"""Firebase Cloud Messaging (FCM) サービス。

プッシュ通知の送信とFCMトークンの管理を行います。
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

from gateway.domain.models import PushNotificationRequest, WebhookPayload
from gateway.infrastructure.repositories import PushTokenRepository

logger = logging.getLogger(__name__)


class FcmService:
    """Firebase Cloud Messaging サービスクラス。

    FCMを通じてプッシュ通知を送信します。
    """

    def __init__(
        self,
        token_repository: PushTokenRepository,
        fcm_project_id: str | None = None,
        fcm_credentials_path: str | None = None,
    ) -> None:
        """FCMサービスを初期化します。

        Args:
            token_repository: トークンリポジトリ
            fcm_project_id: FCMプロジェクトID（オプション）

        Note:
            fcm_project_idが指定されない場合は、デフォルト認証情報を使用します。
        """
        self._token_repository = token_repository
        self._initialized = False
        self._fcm_credentials_path = fcm_credentials_path

        if fcm_project_id:
            try:
                # Firebase Admin SDKの初期化
                if not firebase_admin._apps:
                    cred = self._build_credentials(fcm_credentials_path)
                    firebase_admin.initialize_app(cred, {"projectId": fcm_project_id})
                    logger.info(
                        "Firebase Admin SDK initialized with project: %s",
                        fcm_project_id,
                    )
                self._initialized = True
            except (ValueError, IOError) as e:
                logger.warning("Failed to initialize Firebase Admin SDK: %s", e)
                logger.warning("Push notifications will be disabled")
        else:
            logger.info("FCM project ID not configured. Push notifications disabled")

    def _build_credentials(self, fcm_credentials_path: str | None):
        """Firebase認証情報を構築します。"""
        if fcm_credentials_path:
            credentials_file = Path(fcm_credentials_path)
            if not credentials_file.exists():
                raise FileNotFoundError(
                    f"FCM credentials file not found: {fcm_credentials_path}. "
                    "Please check FCM_CREDENTIALS_PATH environment variable."
                )
            if not credentials_file.is_file():
                raise ValueError(
                    f"FCM credentials path is not a file: {fcm_credentials_path}"
                )
            logger.info(
                "Using Firebase service account credentials: %s",
                credentials_file,
            )
            return credentials.Certificate(str(credentials_file))

        return credentials.ApplicationDefault()

    async def send_notification(
        self,
        device_tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """プッシュ通知を送信します。

        Args:
            device_tokens: 送信先のFCMデバイストークンリスト
            title: 通知タイトル
            body: 通知本文
            data: 通知データ（オプション）

        Returns:
            送信結果を含む辞書
            {
                "success_count": 成功数,
                "failure_count": 失敗数,
                "invalid_tokens": 無効なトークンリスト
            }

        Note:
            無効なトークンは自動的にデータベースで無効化されます。
        """
        if not self._initialized:
            logger.warning("FCM not initialized, skipping notification send")
            return {
                "success_count": 0,
                "failure_count": len(device_tokens),
                "invalid_tokens": [],
            }

        if not device_tokens:
            logger.warning("No device tokens provided")
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # マルチキャストメッセージの作成
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=device_tokens,
        )

        try:
            # FCMに送信（ブロッキング呼び出しを別スレッドで実行）
            response: messaging.BatchResponse = await asyncio.to_thread(
                messaging.send_each_for_multicast,
                message,
            )

            success_count = response.success_count
            failure_count = response.failure_count
            invalid_tokens: list[str] = []

            # 失敗したトークンの処理
            if response.responses:
                for idx, resp in enumerate(response.responses):
                    if resp.exception:
                        token = device_tokens[idx]
                        # 無効なトークンを無効化
                        invalid_error_types = tuple(
                            err
                            for err in (
                                getattr(messaging, "UnregisteredError", None),
                                getattr(messaging, "SenderIdMismatchError", None),
                            )
                            if isinstance(err, type)
                        )
                        is_known_invalid = bool(
                            invalid_error_types
                            and isinstance(resp.exception, invalid_error_types)
                        )
                        is_invalid_value_error = isinstance(
                            resp.exception, ValueError
                        ) and (
                            "InvalidRegistration" in str(resp.exception)
                            or "not a valid FCM registration token"
                            in str(resp.exception)
                        )

                        if is_known_invalid or is_invalid_value_error:
                            await asyncio.to_thread(
                                self._token_repository.disable_token,
                                token,
                            )
                            invalid_tokens.append(token)
                            logger.info(
                                "Disabled invalid token: %s", token[:10] + "..."
                            )
                        else:
                            logger.warning(
                                "Failed to send to token %s: %s",
                                token[:10] + "...",
                                resp.exception,
                            )

            logger.info(
                "Notification sent: success=%d, failure=%d, invalid=%d",
                success_count,
                failure_count,
                len(invalid_tokens),
            )

            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "invalid_tokens": invalid_tokens,
            }

        except Exception:
            logger.exception("Failed to send notification")
            return {
                "success_count": 0,
                "failure_count": len(device_tokens),
                "invalid_tokens": [],
            }

    async def send_to_user(
        self,
        user_id: str,
        notification: PushNotificationRequest,
    ) -> dict[str, Any]:
        """ユーザーの全デバイスにプッシュ通知を送信します。

        Args:
            user_id: ユーザーID
            notification: 通知リクエスト

        Returns:
            送信結果を含む辞書
        """
        # ユーザーのトークンを取得
        devices = await asyncio.to_thread(self._token_repository.get_tokens, user_id)

        if not devices:
            logger.warning("No active devices found for user: %s", user_id)
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        device_tokens = [d.device_token for d in devices]

        # 通知送信
        return await self.send_notification(
            device_tokens=device_tokens,
            title=notification.title,
            body=notification.body,
            data=notification.data,
        )

    async def handle_webhook(
        self, payload: WebhookPayload, user_id: str
    ) -> dict[str, Any]:
        """Webhookペイロードを処理してプッシュ通知を送信します。

        Args:
            payload: Webhookペイロード
            user_id: ユーザーID

        Returns:
            送信結果を含む辞書

        Raises:
            ValidationError: ペイロードのバリデーションに失敗した場合
        """
        # ペイロードのバリデーション
        # payloadは既にWebhookPayload型であることを想定
        validated = payload

        # 通知リクエストを作成
        try:
            notification = PushNotificationRequest(
                title=validated.title,
                body=validated.body,
                data={
                    "type": validated.type,
                    "session_id": validated.session_id,
                    "body": validated.body,
                },
            )
        except Exception:
            logger.exception("Failed to create notification request from payload")
            raise

        # ユーザーに送信
        return await self.send_to_user(user_id, notification)
