import os
import lpips
import torch
from PIL import Image
import torchvision.transforms as transforms

# 初始化LPIPS模型
loss_fn = lpips.LPIPS(net='alex', version='0.1')
def main(folder1_path, folder2_path):
    # 获取文件夹中的图片文件列表
    folder1_images = [os.path.join(folder1_path, f) for f in os.listdir(folder1_path) if
                      os.path.isfile(os.path.join(folder1_path, f))]
    folder2_images = [os.path.join(folder2_path, f) for f in os.listdir(folder2_path) if
                      os.path.isfile(os.path.join(folder2_path, f))]

    # 定义图像转换
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor()
    ])

    # 计算LPIPS值
    total_lpips = 0.0
    count = 0

    for img1_path, img2_path in zip(folder1_images, folder2_images):
        # 打开图像
        img1 = Image.open(img1_path).convert('RGB')
        img2 = Image.open(img2_path).convert('RGB')

        # 应用转换
        img1_tensor = transform(img1).unsqueeze(0)  # 添加 batch 维度
        img2_tensor = transform(img2).unsqueeze(0)  # 添加 batch 维度

        # 计算LPIPS值
        lpips_value = loss_fn(img1_tensor, img2_tensor)

        total_lpips += lpips_value.item()
        count += 1

    # 计算平均LPIPS值
    if count > 0:
        avg_lpips = total_lpips / count
        print("Average LPIPS value: {:.4f}".format(avg_lpips))
    else:
        print("No images found in the folders.")

if __name__ == '__main__':
    input_path = r'IAT/a'
    GT_path =    r'A_inputa_GT'

    main(input_path, GT_path)



