
tmux new-session -d -s ego-graph \; split-window -h \; send-keys 'uv run uvicorn egograph.backend.main:app --reload' C-m \; select-pane -t 0 \; send-keys 'cd frontend && npm run dev' C-m \; attach
