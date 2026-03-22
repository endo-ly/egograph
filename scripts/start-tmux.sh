tmux new-session -d -s fastapi 'uv run python -m backend.main'
tmux new-session -d -s gateway 'uv run python -m gateway.main'
tmux new-session -d -s agent-0001
tmux new-session -d -s agent-0002
tmux new-session -d -s agent-0003
tmux new-session -d -s agent-0004

