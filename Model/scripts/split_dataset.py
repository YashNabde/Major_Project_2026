import os
import shutil
import random

# Path to your dataset
BASE_DIR = os.path.join("datasets", "plates")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
LABELS_DIR = os.path.join(BASE_DIR, "labels")

# Make folders for YOLOv8 structure
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(IMAGES_DIR, split), exist_ok=True)
    os.makedirs(os.path.join(LABELS_DIR, split), exist_ok=True)

# Train/Val/Test split ratio
TRAIN_RATIO = 0.7
VAL_RATIO = 0.2
TEST_RATIO = 0.1  # remainder

image_files = [
    f for f in os.listdir(IMAGES_DIR)
    if f.lower().endswith((".jpg", ".jpeg", ".png"))
]

random.shuffle(image_files)

n = len(image_files)
train_end = int(TRAIN_RATIO * n)
val_end = train_end + int(VAL_RATIO * n)

train_files = image_files[:train_end]
val_files = image_files[train_end:val_end]
test_files = image_files[val_end:]

def move_files(files_list, split_name):
    for img_file in files_list:
        src_img = os.path.join(IMAGES_DIR, img_file)
        dst_img = os.path.join(IMAGES_DIR, split_name, img_file)

        label_file = os.path.splitext(img_file)[0] + ".txt"
        src_label = os.path.join(LABELS_DIR, label_file)
        dst_label = os.path.join(LABELS_DIR, split_name, label_file)

        # Move image
        if os.path.exists(src_img):
            shutil.move(src_img, dst_img)

        # Move label (if exists)
        if os.path.exists(src_label):
            shutil.move(src_label, dst_label)

move_files(train_files, "train")
move_files(val_files, "val")
move_files(test_files, "test")

print("Dataset split completed successfully!")
print(f"Train: {len(train_files)}, Val: {len(val_files)}, Test: {len(test_files)}")
