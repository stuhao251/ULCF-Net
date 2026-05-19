import torchvision.transforms
from unicodedata import name
import cv2
import numpy as np
from skimage.metrics import structural_similarity, peak_signal_noise_ratio
import os
import torch
import torchvision.transforms.functional as TF
from pytorch_msssim import ssim
from torch.autograd import Variable
from torchvision.transforms import ToTensor
from PIL import Image
import math
from scipy import ndimage
def _uiconm(x, window_size):
    """
      Underwater image contrast measure
      https://github.com/tkrahn108/UIQM/blob/master/src/uiconm.cpp
      https://ieeexplore.ieee.org/abstract/document/5609219
    """
    plip_lambda = 1026.0
    plip_gamma = 1026.0
    plip_beta = 1.0
    plip_mu = 1026.0
    plip_k = 1026.0
    # if 4 blocks, then 2x2...etc.
    k1 = x.shape[1] / window_size
    k2 = x.shape[0] / window_size
    # weight
    w = -1. / (k1 * k2)
    blocksize_x = window_size
    blocksize_y = window_size
    # make sure image is divisible by window_size - doesn't matter if we cut out some pixels
    x = x[0:int(blocksize_y * k2), 0:int(blocksize_x * k1)]
    # entropy scale - higher helps with randomness
    alpha = 1
    val = 0
    k1 = int(k1)
    k2 = int(k2)
    for l in range(k1):
        for k in range(k2):
            block = x[k * window_size:window_size * (k + 1), l * window_size:window_size * (l + 1), :]
            max_ = np.max(block)
            min_ = np.min(block)
            top = max_ - min_
            bot = max_ + min_
            if math.isnan(top) or math.isnan(bot) or bot == 0.0 or top == 0.0:
                val += 0.0
            else:
                val += alpha * math.pow((top / bot), alpha) * math.log(top / bot)
            # try: val += plip_multiplication((top/bot),math.log(top/bot))
    return w * val


def mu_a(x, alpha_L=0.1, alpha_R=0.1):
    """
      Calculates the asymetric alpha-trimmed mean
    """
    # sort pixels by intensity - for clipping
    x = sorted(x)
    # get number of pixels
    K = len(x)
    # calculate T alpha L and T alpha R
    T_a_L = math.ceil(alpha_L * K)
    T_a_R = math.floor(alpha_R * K)
    # calculate mu_alpha weight
    weight = (1 / (K - T_a_L - T_a_R))
    # loop through flattened image starting at T_a_L+1 and ending at K-T_a_R
    s = int(T_a_L + 1)
    e = int(K - T_a_R)
    val = sum(x[s:e])
    val = weight * val
    return val


def s_a(x, mu):
    val = 0
    for pixel in x:
        val += math.pow((pixel - mu), 2)
    return val / len(x)


def _uicm(x):
    R = x[:, :, 0].flatten()
    G = x[:, :, 1].flatten()
    B = x[:, :, 2].flatten()
    RG = R - G
    YB = ((R + G) / 2) - B
    mu_a_RG = mu_a(RG)
    mu_a_YB = mu_a(YB)
    s_a_RG = s_a(RG, mu_a_RG)
    s_a_YB = s_a(YB, mu_a_YB)
    l = math.sqrt((math.pow(mu_a_RG, 2) + math.pow(mu_a_YB, 2)))
    r = math.sqrt(s_a_RG + s_a_YB)
    return (-0.0268 * l) + (0.1586 * r)


def sobel(x):
    dx = ndimage.sobel(x, 0)
    dy = ndimage.sobel(x, 1)
    mag = np.hypot(dx, dy)
    mag *= 255.0 / np.max(mag)
    return mag


def _uism(x):
    """
      Underwater Image Sharpness Measure
    """
    # get image channels
    R = x[:, :, 0]
    G = x[:, :, 1]
    B = x[:, :, 2]
    # first apply Sobel edge detector to each RGB component
    Rs = sobel(R)
    Gs = sobel(G)
    Bs = sobel(B)
    # multiply the edges detected for each channel by the channel itself
    R_edge_map = np.multiply(Rs, R)
    G_edge_map = np.multiply(Gs, G)
    B_edge_map = np.multiply(Bs, B)
    # get eme for each channel
    r_eme = eme(R_edge_map, 10)
    g_eme = eme(G_edge_map, 10)
    b_eme = eme(B_edge_map, 10)
    # coefficients
    lambda_r = 0.299
    lambda_g = 0.587
    lambda_b = 0.144
    return (lambda_r * r_eme) + (lambda_g * g_eme) + (lambda_b * b_eme)


def eme(x, window_size):
    """
      Enhancement measure estimation
      x.shape[0] = height
      x.shape[1] = width
    """
    # if 4 blocks, then 2x2...etc.
    k1 = x.shape[1] / window_size
    k2 = x.shape[0] / window_size
    # weight
    w = 2. / (k1 * k2)
    blocksize_x = window_size
    blocksize_y = window_size
    # make sure image is divisible by window_size - doesn't matter if we cut out some pixels
    x = x[0:int(blocksize_y * k2), 0:int(blocksize_x * k1)]
    val = 0
    k1 = int(k1)
    k2 = int(k2)
    for l in range(k1):
        for k in range(k2):
            block = x[k * window_size:window_size * (k + 1), l * window_size:window_size * (l + 1)]
            max_ = np.max(block)
            min_ = np.min(block)
            # bound checks, can't do log(0)
            if min_ == 0.0:
                val += 0
            elif max_ == 0.0:
                val += 0
            else:
                val += math.log(max_ / min_)
    return w * val


def calc_uiqm(img: Image):
    """
      Function to return UIQM to be called from other programs
      x: image
    """
    x = img.copy()
    x = np.array(x)
    x = x.astype(np.float32)
    ### UCIQE: https://ieeexplore.ieee.org/abstract/document/7300447
    # c1 = 0.4680;
    # c2 = 0.2745;
    # c3 = 0.2576
    ### UIQM https://ieeexplore.ieee.org/abstract/document/7305804
    c1 = 0.0282
    c2 = 0.2953
    c3 = 3.5753
    uicm = _uicm(x)
    uism = _uism(x)
    uiconm = _uiconm(x, 10)
    uiqm = (c1 * uicm) + (c2 * uism) + (c3 * uiconm)
    return uiqm

def calc_uciqe(img: Image, nargin: int = 1):
    img_clone = img.copy()
    img_bgr = cv2.cvtColor(np.array(img_clone), cv2.COLOR_RGB2BGR)
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)  # Transform to Lab color space

    if nargin == 1:  # According to training result mentioned in the paper:
        coe_metric = [0.4680, 0.2745, 0.2576]  # Obtained coefficients are: c1=0.4680, c2=0.2745, c3=0.2576.
    img_lum = img_lab[..., 0] / 255
    img_a = img_lab[..., 1] / 255
    img_b = img_lab[..., 2] / 255

    img_chr = np.sqrt(np.square(img_a) + np.square(img_b))  # Chroma

    img_sat = img_chr / np.sqrt(np.square(img_chr) + np.square(img_lum))  # Saturation
    aver_sat = np.mean(img_sat)  # Average of saturation

    aver_chr = np.mean(img_chr)  # Average of Chroma

    var_chr = np.sqrt(np.mean(abs(1 - np.square(aver_chr / img_chr))))  # Variance of Chroma

    dtype = img_lum.dtype  # Determine the type of img_lum
    if dtype == 'uint8':
        nbins = 256
    else:
        nbins = 65536

    hist, bins = np.histogram(img_lum, nbins)  # Contrast of luminance
    cdf = np.cumsum(hist) / np.sum(hist)

    ilow = np.where(cdf > 0.0100)
    ihigh = np.where(cdf >= 0.9900)
    tol = [(ilow[0][0] - 1) / (nbins - 1), (ihigh[0][0] - 1) / (nbins - 1)]
    con_lum = tol[1] - tol[0]

    quality_val = coe_metric[0] * var_chr + coe_metric[1] * con_lum + coe_metric[
        2] * aver_sat  # get final quality value
    return np.float(quality_val)

def ComputePSNR_SSIM(img_dir):
    error_list_UIQM, error_list_UCIQE =  [], []
    for dir_path in img_dir:
        enhanced_name = dir_path.split('/')[-1]
        # gt_name = enhanced_name
        enhanced = cv2.imread(dir_path)
        enhanced = cv2.resize(enhanced, (256, 256))
        # gt = cv2.imread(os.path.join(gt_path, gt_name))
        # error_ssim = SSIM(enhanced, gt)
        # gt = TF.to_tensor(gt)
        # enhanced = TF.to_tensor(enhanced)
        # error_psnr = torchPSNR(gt, enhanced)
        error_UIQM = calc_uiqm(enhanced)
        error_UCIQE = calc_uciqe(enhanced)
        # gt = gt.unsqueeze(0)
        # enhanced = enhanced.unsqueeze(0)
        # error_psnr = psnr(enhanced, gt)
        # error_ssim = torchSSIM(gt,enhanced)
        print(enhanced_name, error_UIQM, error_UCIQE)
        error_list_UIQM.append(error_UIQM)
        error_list_UCIQE.append(error_UCIQE)
        # error_list_mse.append(error_mse)
    return np.array(error_list_UIQM), np.array(error_list_UCIQE)#, np.array(error_list_mse)

if __name__=='__main__':
    enhanced_path = r'IAT/c'

    img_name = os.listdir(enhanced_path)
    img_dir = [ os.path.join(enhanced_path,name) for name in img_name]
    uiqms,uciqes = ComputePSNR_SSIM(img_dir)
    print ("UIQM >> Mean: {:.4f} std: {:.4f}".format(np.mean(uiqms), np.std(uiqms)))
    print ("UCIQE >> Mean: {:.4f} std: {:.4f}".format(np.mean(uciqes), np.std(uciqes)))

