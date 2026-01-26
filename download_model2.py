from huggingface_hub import snapshot_download
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

# ... rồi snapshot_download như cũ

# Chọn 1 trong các repo_id dưới đây:
# repo_id = "ResembleAI/chatterbox"              # bản gốc ~500M, chất lượng cao
repo_id = "ResembleAI/chatterbox-turbo"        # turbo, nhanh, nhẹ hơn (~350M)
# repo_id = "ResembleAI/chatterbox-multilingual" # nếu cần đa ngôn ngữ (23 ngôn ngữ)

local_dir = "pretrained_models/chatterbox-turbo"  # folder bạn muốn lưu

snapshot_download(
    repo_id=repo_id,
    local_dir=local_dir,
    local_dir_use_symlinks=False,   # Windows/macOS nên False để copy file thật
    ignore_patterns=["*.msgpack", "*.h5"],  # bỏ file không cần nếu có
    max_workers = 8
)

print(f"Đã tải xong Chatterbox vào: {local_dir}")