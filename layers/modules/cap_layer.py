# Finger crossed!
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import time


def softmax_dim(input, axis=1):
    input_size = input.size()

    trans_input = input.transpose(axis, len(input_size)-1)
    trans_size = trans_input.size()

    input_2d = trans_input.contiguous().view(-1, trans_size[-1])

    soft_max_2d = F.softmax(input_2d)

    soft_max_nd = soft_max_2d.view(*trans_size)
    return soft_max_nd.transpose(axis, len(input_size)-1)


def squash(vec):
    # vec: 128 x 10 x 16
    norm = vec.norm(dim=2)
    norm_squared = norm ** 2
    coeff = norm_squared / (1 + norm_squared)
    coeff2 = torch.unsqueeze((coeff/norm), dim=2)
    # coeff2: 128 x 10 x 1
    return torch.mul(vec, coeff2)


class CapLayer(nn.Module):
    def __init__(self, num_in_caps, num_out_caps,
                 in_dim, out_dim, num_shared,
                 route_num, b_init, w_version,
                 do_squash=False, look_into_details=False):
        super(CapLayer, self).__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.num_shared = num_shared
        self.route_num = route_num
        self.w_version = w_version
        self.num_out_caps = num_out_caps
        self.look_into_details = look_into_details
        if self.look_into_details:
            self.which_sample, self.which_j = 0, 3

        if w_version == 'v0':
            self.W = [nn.Linear(in_dim, out_dim, bias=False) for _ in range(num_shared)]
        elif w_version == 'v1':
            # 1152 (32 x 36), 8, 16, 10
            # W[x][y], x = 32, y = 10
            self.W = [[nn.Linear(in_dim, out_dim, bias=False)] * num_out_caps for _ in range(num_shared)]
        elif w_version == 'v2':
            # faster
            self.W = nn.Conv2d(256, num_shared*num_out_caps*out_dim,
                               kernel_size=1, stride=1, groups=num_shared)
            # self.relu = nn.ReLU(True)
        elif w_version == 'v3':
            # for fair comparison
            self.avgpool = nn.AvgPool2d(6)
            self.fc = nn.Linear(256, 160)
            self.do_squash = do_squash

        if b_init == 'rand':
            self.b = Variable(torch.rand(num_out_caps, num_in_caps), requires_grad=False)
        elif b_init == 'zero':
            self.b = Variable(torch.zeros(num_out_caps, num_in_caps), requires_grad=False)

    def forward(self, input, target):
        if target is not None and self.look_into_details:
            self.which_j = target[self.which_sample].data[0]
        bs, in_channels, h, w = input.size()
        # assert in_channels == self.num_shared * self.in_dim
        b = self.b.expand(bs, self.b.size(0), self.b.size(1))  # expand b_ji along batch dim

        if self.w_version == 'v1' or self.w_version == 'v2':
            # start = time.time()
            if self.w_version == 'v1':
                input = input.view(bs, self.num_shared, -1, self.in_dim)
                groups = input.chunk(self.num_shared, dim=1)
                u = [group.chunk(h * w, dim=2) for group in groups]
                # self.W[3][zz](u[3][0]), u[i][j], i = 1...32, j = 1...36, zz = 10
                pred = [self.W[i][zz](in_vec) for zz in range(self.num_out_caps)
                        for i, group in enumerate(u) for in_vec in group]
                # pred, list[11520], each entry, Variable, size [128x1x1x16]
                pred = torch.stack(pred).permute(1, 0, 2, 3, 4).squeeze()
                # pred: [128, 1152, 10, 16]
                pred = pred.resize(pred.size(0), int(pred.size(1)/self.num_out_caps),
                                   self.num_out_caps, pred.size(2))
            elif self.w_version == 'v2':
                raw_output = self.W(input)
                # bs x 5120 x 6 x 6 -> bs x 32 x 10 x 16 x 6 x 6 -> bs x 32 x 6 x 6 x 10 x 16
                spatial_size = raw_output.size(2)
                raw_output_1 = raw_output.resize(bs,
                                                 self.num_shared, self.num_out_caps, self.out_dim,
                                                 spatial_size, spatial_size).permute(0, 1, 4, 5, 2, 3)
                pred = raw_output_1.resize(bs,
                                           self.num_shared*spatial_size*spatial_size, self.num_out_caps, self.out_dim)
                # pred = self.relu(pred)  # NO relu here!
            # print('cap W time: {:.4f}'.format(time.time() - start))

            if self.look_into_details:
                print('u_hat:'), print(pred[self.which_sample, :, self.which_j, :])
            # start = time.time()
            for i in range(self.route_num):

                c = softmax_dim(b, axis=1)              # 128 x 10 x 1152, c_nji, \sum_j = 1
                temp_ = [torch.matmul(c[:, zz, :].unsqueeze(dim=1), pred[:, :, zz, :].squeeze()).squeeze()
                         for zz in range(self.num_out_caps)]
                s = torch.stack(temp_, dim=1)
                v = squash(s)                           # 128 x 10 x 16
                temp_ = [torch.matmul(v[:, zz, :].unsqueeze(dim=1), pred[:, :, zz, :].permute(0, 2, 1)).squeeze()
                         for zz in range(self.num_out_caps)]
                delta_b = torch.stack(temp_, dim=1).detach()
                if self.look_into_details:
                    print('[{:d}/{:d}] b:'.format(i, self.route_num))
                    print(b[self.which_sample, self.which_j, :])
                    print('[{:d}/{:d}] c:'.format(i, self.route_num))
                    print(c[self.which_sample, self.which_j, :])
                    print('[{:d}/{:d}] v:'.format(i, self.route_num))
                    print(v[self.which_sample, self.which_j, :])
                    print('[{:d}/{:d}] v all classes:'.format(i, self.route_num))
                    print(v[self.which_sample, :, :].norm(dim=1))
                    print('[{:d}/{:d}] delta_b:'.format(i, self.route_num))
                    print(delta_b[self.which_sample, self.which_j, :])
                    print('\n')

                b = torch.add(b, delta_b)
            # print('cap Route (r={:d}) time: {:.4f}'.format(self.route_num, time.time() - start))
        elif self.w_version == 'v0':
            input = input.view(bs, self.num_shared, -1, self.in_dim)
            groups = input.chunk(self.num_shared, dim=1)
            u = [group.chunk(h * w, dim=2) for group in groups]
            # self.W[1](u[1][0]), u[i][j], i = 1...32, j = 1...36
            pred = [self.W[i](in_vec) for i, group in enumerate(u) for in_vec in group]
            # pred, list[1152], each entry, Variable, size [128x1x1x16]
            pred = torch.stack(pred).permute(1, 0, 2, 3, 4).squeeze()  # \hat(s)_j -> 128, 1152, 16

            for i in range(self.route_num):
                # print('b'), print(b[0, 0:3, :])
                c = softmax_dim(b, axis=1)              # 128 x 10 x 1152, c_nji, \sum_j = 1
                # print('c'), print(c[0, 0:3, :])
                s = torch.matmul(c, pred)               # 128 x 10 x 16
                v = squash(s)
                delta_b = torch.matmul(pred, v.permute(0, 2, 1)).permute(0, 2, 1)
                # print('delta_b'), print(delta_b[0, 0:3, :])
                b = torch.add(b, delta_b)
        elif self.w_version == 'v3':
            x = self.avgpool(input)
            x = x.view(x.size(0), -1)
            x = self.fc(x)
            v = x.resize(bs, self.num_out_caps, self.out_dim)
            if self.do_squash:
                v = squash(v)
        return v


class MarginLoss(nn.Module):

    def __init__(self, num_classes, pos=0.9, neg=0.1, lam=0.5):
        super(MarginLoss, self).__init__()
        self.num_classes = num_classes
        self.pos = pos
        self.neg = neg
        self.lam = lam

    def forward(self, output, target):
        # norm = output.norm(dim=2)        # 128 x 10
        gt = Variable(torch.zeros(output.size(0), self.num_classes), requires_grad=False)
        gt = gt.scatter_(1, target.unsqueeze(1), 1)
        zero = Variable(torch.zeros(1))
        pos_part = torch.max(zero, self.pos - output).pow(2)
        neg_part = torch.max(zero, output - self.neg).pow(2)
        loss = gt * pos_part + self.lam * (1-gt) * neg_part
        return loss.sum() / output.size(0)
