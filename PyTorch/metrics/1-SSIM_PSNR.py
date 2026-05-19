import argparse
import os
import cv2
import numpy as np
import torch
from pytorch_msssim import ssim
import torchvision.transforms.functional as TF


def mse(imageA, imageB):
    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    # NOTE: the two images must have the same dimension
    # print(imageA - imageB)
    err = torch.sum((imageA - imageB) ** 2)
    # print(err)
    err /= imageA.shape[2] * imageA.shape[3]

    # return the MSE, the lower the error, the more "similar"
    # the two images are
    return err

def torchPSNR(tar_img, prd_img):
    imdff = torch.clamp(prd_img, 0, 1) - torch.clamp(tar_img, 0, 1)
    rmse = (imdff**2).mean().sqrt()
    ps = 20*torch.log10(1/rmse)
    return ps

def torchSSIM(tar_img, prd_img):
    return ssim(tar_img, prd_img, data_range=1.0, size_average=True)

def main(im_path, re_path):
    # PSNRs, SSIMs= [], []
    MSEs, PSNRs, SSIMs= [], [], []
    n = 0

    for filename in os.listdir(im_path):
        print(im_path + '/' + filename)
        n = n + 1
        im1 = cv2.imread(im_path + '/' + filename)
        im2 = cv2.imread(re_path + '/' + filename)

        im1 = torch.tensor(im1/255.0).permute(2, 0, 1).unsqueeze(0).to('cuda:0')
        im2 = torch.tensor(im2/255.0).permute(2, 0, 1).unsqueeze(0).to('cuda:0')

        im1 = TF.resize(im1, [256, 256])
        im2 = TF.resize(im2, [256, 256])
        MSEs.append(mse(im1, im2))
        PSNRs.append(torchPSNR(im1, im2))
        SSIMs.append(torchSSIM(im1, im2))
    print("[PSNR] mean: {:.4f} std: {:.4f}".format(torch.stack(PSNRs).mean().item(), torch.stack(PSNRs).std().item()))
    print("[SSIM] mean: {:.4f} std: {:.4f}".format(torch.stack(SSIMs).mean().item(), torch.stack(SSIMs).std().item()))
    print("[MSE] mean: {:.4f} std: {:.4f}".format(torch.stack(MSEs).mean().item(), torch.stack(MSEs).std().item()))

if __name__ == '__main__':
    input_dir = r'IAT/a'
    reference_dir = r'A_inputa_GT'

    parser = argparse.ArgumentParser(description='Performance')
    parser.add_argument('--input_dir', default=input_dir)
    parser.add_argument('--reference_dir', default=reference_dir)
    opt = parser.parse_args()
    im_path = opt.input_dir
    re_path = opt.reference_dir
    print(opt)

    main(im_path, re_path)