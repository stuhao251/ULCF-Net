import os
import cv2
import torch
import pyiqa

# 初始化 U-Ranker 评价指标
uranker_metric = pyiqa.create_metric('uranker')


def calculate_uranker_index(img_path):
    """计算单张图片的 U-Ranker 评分"""
    img = cv2.imread(img_path)  # 读取图像
    if img is None:
        print(f"Error: Cannot read image {img_path}")
        return None

    img = cv2.resize(img, (256, 256))  # 调整大小
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # BGR 转 RGB
    img = img.astype("float32") / 255.0  # 归一化到 [0,1]

    # 转换为 PyTorch tensor，并调整通道顺序 (C, H, W)
    img_tensor = torch.tensor(img).permute(2, 0, 1).unsqueeze(0)  # (1, C, H, W)

    # 计算 U-Ranker 评分
    score = uranker_metric(img_tensor).item()
    return score


def process_folder(img_folder, output_file):
    """批量计算文件夹内所有图片的 U-Ranker 评分，并计算平均值"""
    results = []

    # 遍历文件夹中的所有图片
    for filename in os.listdir(img_folder):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):  # 只处理图片
            img_path = os.path.join(img_folder, filename)
            score = calculate_uranker_index(img_path)
            if score is not None:
                results.append((filename, score))
                print(f"{filename}: {score:.4f}")

    if not results:
        print("No valid images found in the folder.")
        return

    # 评分按高到低排序
    results.sort(key=lambda x: x[1], reverse=True)

    # 计算平均分
    avg_score = sum(score for _, score in results) / len(results)

    # 将结果保存到文件
    with open(output_file, 'w') as f:
        for filename, score in results:
            f.write(f"{filename}: {score:.4f}\n")
        f.write(f"\nAverage U-Ranker Score: {avg_score:.4f}\n")

    print(f"\nAverage U-Ranker Score: {avg_score:.4f}")
    print(f"U-Ranker scores saved to {output_file}")




def main(img_folder, output_file):
    process_folder(img_folder, output_file)


if __name__ == "__main__":
    img_folder =  r'WaveNet-T/od'  # 你要处理的文件夹
    output_file = r'WaveNet-T/od.txt'  # 结果保存路径

    main(img_folder, output_file)
