import cv2
import os

# 设置输入和输出文件夹
input_folder =  r"DMfourllie/a/output"  # 原始图片文件夹
output_folder = r"DMfourllie/a_canny"  # 处理后图片保存的文件夹

# 确保输出文件夹存在
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 读取输入文件夹中的所有文件
for filename in os.listdir(input_folder):
    input_path = os.path.join(input_folder, filename)
    output_path = os.path.join(output_folder, filename)

    # 只处理图片文件
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        # 读取图片并转换为灰度图
        img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)

        if img is None:
            print(f"跳过无法读取的文件: {filename}")
            continue

        # Canny 边缘检测
        edges = cv2.Canny(img, 50, 150)

        # 保存处理后的图片
        cv2.imwrite(output_path, edges)
        print(f"处理完成: {filename} -> {output_path}")

print("所有图片处理完成！")
