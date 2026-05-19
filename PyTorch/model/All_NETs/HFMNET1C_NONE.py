import torch
import torch.nn as nn
import torch.nn.functional as F

class PS_down(nn.Module):
    def __init__(self, in_size, out_size, downscale):
        super(PS_down, self).__init__()
        self.UnPS = nn.PixelUnshuffle(downscale)
        self.conv1 = nn.Conv2d((downscale**2) * in_size, out_size, 1, 1, 0)

    def forward(self, x):
        x = self.UnPS(x)  # h/2, w/2, 4*c
        x = self.conv1(x)
        return x
class PS_up(nn.Module):
    def __init__(self, in_size, out_size, upscale):
        super(PS_up, self).__init__()

        self.PS = nn.PixelShuffle(upscale)
        self.conv1 = nn.Conv2d(in_size//(upscale**2), out_size, 1, 1, 0)

    def forward(self, x):
        x = self.PS(x)  # h/2, w/2, 4*c
        x = self.conv1(x)
        return x
class SKFFv2(nn.Module):
    def __init__(self, in_channels, height=4, reduction=8, bias=False):
        super(SKFFv2, self).__init__()

        self.height = height
        d = max(int(in_channels / reduction), 4)

        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv_du = nn.Sequential(
            nn.Conv2d(in_channels, d, 1, padding=0, bias=bias),
            nn.PReLU())

        self.fcs = nn.ModuleList([])
        for i in range(self.height):
            self.fcs.append(  nn.Conv2d(d, in_channels, kernel_size=1, stride=1, bias=bias)  )

        self.softmax = nn.Softmax(dim=1)

    def forward(self, inp_feats):
        #print(inp_feats[0].shape,inp_feats[1].shape,inp_feats[2].shape,inp_feats[3].shape)
        batch_size, n_feats, H, W = inp_feats[1].shape
        inp_feats = torch.cat(inp_feats, dim=1)
        inp_feats = inp_feats.view(batch_size, self.height, n_feats, inp_feats.shape[2], inp_feats.shape[3])
        #bracnh1
        feats_U1 = torch.sum(inp_feats, dim=1)
        feats_S1 = self.avg_pool(feats_U1)
        feats_Z1 = self.conv_du(feats_S1)
        attention_vectors1 = [fc(feats_Z1) for fc in self.fcs]
        attention_vectors1 = torch.cat(attention_vectors1, dim=1)
        attention_vectors1 = attention_vectors1.view(batch_size, self.height, n_feats, 1, 1)
        attention_vectors1 = self.softmax(attention_vectors1)

        #branch2
        feats_U2 = torch.sum(inp_feats, dim=1)
        feats_S2 = self.avg_pool(feats_U2)
        feats_Z2 = self.conv_du(feats_S2)
        attention_vectors2 = [fc(feats_Z2) for fc in self.fcs]
        attention_vectors2 = torch.cat(attention_vectors2, dim=1)
        attention_vectors2 = attention_vectors2.view(batch_size, self.height, n_feats, 1, 1)
        attention_vectors2 = self.softmax(attention_vectors2)

        feats_V = torch.sum(inp_feats * attention_vectors1*attention_vectors2, dim=1)
        return feats_V
class SKFF(nn.Module):
    def __init__(self, in_channels, height=4, reduction=8, bias=False):
        super(SKFF, self).__init__()

        self.height = height
        d = max(int(in_channels / reduction), 4)

        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv_du = nn.Sequential(nn.Conv2d(in_channels, d, 1, padding=0, bias=bias), nn.PReLU())

        self.fcs = nn.ModuleList([])
        for i in range(self.height):
            self.fcs.append(nn.Conv2d(d, in_channels, kernel_size=1, stride=1, bias=bias))

        self.softmax = nn.Softmax(dim=1)

    def forward(self, inp_feats):
        batch_size, n_feats, H, W = inp_feats[1].shape

        inp_feats = torch.cat(inp_feats, dim=1)
        inp_feats = inp_feats.view(batch_size, self.height, n_feats, inp_feats.shape[2], inp_feats.shape[3])

        feats_U = torch.sum(inp_feats, dim=1)
        feats_S = self.avg_pool(feats_U)
        feats_Z = self.conv_du(feats_S)

        attention_vectors = [fc(feats_Z) for fc in self.fcs]
        attention_vectors = torch.cat(attention_vectors, dim=1)
        attention_vectors = attention_vectors.view(batch_size, self.height, n_feats, 1, 1)

        attention_vectors = self.softmax(attention_vectors)
        feats_V = torch.sum(inp_feats * attention_vectors, dim=1)

        return feats_V
class FFTB(nn.Module):
    def __init__(self, n_feats):
        super().__init__()
        # i_feats =n_feats*2
        self.GlobalAveragePolling = nn.AdaptiveAvgPool2d(1)
        self.convBlock = nn.Sequential(

            nn.Conv2d(n_feats, n_feats, 1, 1, 0),
            nn.BatchNorm2d(n_feats),
            nn.LeakyReLU(),
        )
        self.conv = nn.Conv2d(n_feats, n_feats, 1, 1, 0)
    def forward(self, x):
        _, _, H, W = x.shape

        fg = self.GlobalAveragePolling(x) #1 c 1  1

        x_freq = torch.fft.rfft2(fg, norm='backward')
        mag = torch.abs(x_freq)  #mag 1 c 1 1       #pha 1 c 1 1
        pha = torch.angle(x_freq)

        fgout = self.convBlock(fg)

        mag *= fgout
        pha *= fgout

        real_main = mag * torch.cos(pha)
        imag_main = mag * torch.sin(pha)
        x_out_main = torch.complex(real_main, imag_main)
        x_out_main = torch.abs(torch.fft.irfft2(x_out_main, s=(H, W), norm='backward')) + 1e-8

        x_out_main = self.conv(x_out_main)

        return x_out_main
class HFB(nn.Module):
    def __init__(self, n_feat, o_feat, kernel_size, bias, act):
        super(HFB, self).__init__()


        self.conv3x3 = nn.Conv2d(n_feat, o_feat, kernel_size=3, padding=1, bias=bias)
        self.activate = act
        self.conv1x1_final = nn.Conv2d(n_feat, o_feat, kernel_size=1, bias=bias)

        self.fftb = FFTB( int(n_feat/2) )

    def forward(self, x):
        residual = x
        # Split 2 part
        wavelet_path_in, identity_path = torch.chunk(x, 2, dim=1)
        wavelet_path = self.fftb(wavelet_path_in)

        out = torch.cat([wavelet_path, identity_path], dim=1)
        out = self.activate(self.conv3x3(out))
        out += self.conv1x1_final(residual)

        return out

class HFMNET(nn.Module):
    def __init__(self,in_chn=3, wf=96):
        super(HFMNET, self).__init__()
        #编码
        self.hfb1 = HFB(n_feat=96, o_feat=96, kernel_size=3, bias=False, act=nn.LeakyReLU())
        self.down1 = PS_down(96,96,2)

        self.hfb2 = HFB(n_feat=192, o_feat=192, kernel_size=3, bias=False, act=nn.LeakyReLU())
        self.down2 = PS_down(192,192,2)

        self.hfb3 = HFB(n_feat=288, o_feat=384, kernel_size=3, bias=False, act=nn.LeakyReLU())
        self.down3 = PS_down(384,384,2)

        self.hfb4 = HFB(n_feat=480, o_feat=768, kernel_size=3, bias=False, act=nn.LeakyReLU())

        #解码
        self.up4 = PS_up(768,384,2)

        self.hfb5 = HFB(n_feat=960, o_feat=384, kernel_size=3, bias=False, act=nn.LeakyReLU())
        self.up3 = PS_up(384, 192, 2)

        self.hfb6 = HFB(n_feat=576, o_feat=192, kernel_size=3, bias=False, act=nn.LeakyReLU())
        self.up2 = PS_up(192, 96, 2)

        self.hfb7 = HFB(n_feat=288, o_feat=96, kernel_size=3, bias=False, act=nn.LeakyReLU())
        #输入分支
        self.conv_first = nn.Sequential(
            
            nn.Conv2d(3, 96, 3, 1, 1))
        self.down_first = nn.Upsample(scale_factor=0.5, mode='bilinear', align_corners=False)
        #输出分支
        self.conv_x4 = nn.Sequential(
            
            nn.Conv2d(768, 96, 3, 1, 1))
        self.conv_x3 = nn.Sequential(
            
            nn.Conv2d(384, 96, 3, 1, 1))
        self.conv_x2 = nn.Sequential(
            
            nn.Conv2d(192, 96, 3, 1, 1))
        self.conv_x1 = nn.Sequential(
            
            nn.Conv2d(96, 96, 3, 1, 1))
        self.up_branch4 = nn.Upsample(scale_factor=8, mode='bilinear', align_corners=False)
        self.up_branch3 = nn.Upsample(scale_factor=4, mode='bilinear', align_corners=False)
        self.up_branch2 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)

        #self.skff = SKFFv2(96, 4)
        #self.skff = SKFF(96, 4)

        self.lastconv = nn.Conv2d(96, 3, kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        skip_updown = []
        skip = []

        x2 = self.down_first(x)
        x3 = self.down_first(x2)
        x4 = self.down_first(x3)
        x1 = self.conv_first(x)   #96 256 256
        x2 = self.conv_first(x2)  #96 128 128
        x3 = self.conv_first(x3)  #96 64 64
        x4 = self.conv_first(x4)  #96 32 32
        #编码
        x1_out = self.hfb1(x1)
        skip.append(x1_out)
        x1_down = self.down1(x1_out)

        x2_out = self.hfb2( torch.cat([x2,x1_down],dim=1) )
        skip.append(x2_out)
        skip_updown.append(self.up2(x2_out))  #2上
        x2_down = self.down2(x2_out)
        skip_updown.append(x2_down)           #2下

        x3_out = self.hfb3( torch.cat([x3, x2_down], dim=1) )
        skip.append(x3_out)
        skip_updown.append(self.up3(x3_out))  #3上
        x3_down = self.down3(x3_out)

        x4_out = self.hfb4(torch.cat([x4, x3_down], dim=1))
        skx4 = self.conv_x4(x4_out)
        #解码
        dx3 = self.up4(x4_out)

        dx3 = self.hfb5( torch.cat([dx3, skip[2],skip_updown[1]], dim=1) )
        skx3 = self.conv_x3(dx3)
        dx2 = self.up3(dx3)

        dx2 = self.hfb6(torch.cat([dx2, skip[1],skip_updown[2]], dim=1))
        skx2 = self.conv_x2(dx2)
        dx1 = self.up2(dx2)

        skx1 = self.hfb7(torch.cat([dx1, skip[0],skip_updown[0]], dim=1))
        skx4 = self.up_branch4(skx4)
        skx3 = self.up_branch3(skx3)
        skx2 = self.up_branch2(skx2)

        #last_out = self.skff([skx1,skx2,skx3,skx4])
        last_out = skx1+skx2+skx3+skx4

        last_out = self.lastconv(last_out)

        return  last_out+x

if __name__=='__main__':
    x = torch.randn(2,3,256,256)
    cdan = HFMNET()
    cdan(x)
    from thop import profile

    flops, params = profile(cdan, inputs=(x,))

    print('parameters:', params / 1e6)  #13M
    print('flops', flops / 1e9)         #169

