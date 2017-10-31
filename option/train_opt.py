import argparse
import os
import torch
import utils.util as util


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")

parser = argparse.ArgumentParser(description='Single Shot MultiBox Detector Training')
parser.add_argument('--version', default='v2', help='conv11_2(v2) or pool6(v1) as last layer')
parser.add_argument('--dataset', default='coco', help='[ voc | coco ]')
parser.add_argument('--experiment_name', default='ssd_base_101')
parser.add_argument('--deploy', action='store_true')

# training config
parser.add_argument('--max_iter', default=130000, type=int, help='Number of training iterations')
parser.add_argument('--no_pretrain', action='store_true', help='default is using pretrain')
parser.add_argument('--basenet', default='vgg16_reducedfc.pth', help='pretrained base model')
parser.add_argument('--resume', default=None, type=str, help='Resume from checkpoint')
# parser.add_argument('--resume', default='ssd300_0712_iter_30', type=str, help='Resume from checkpoint')

parser.add_argument('--batch_size', default=2, type=int, help='Batch size for training')
parser.add_argument('--lr', '--learning-rate', default=1e-5, type=float, help='initial learning rate')
parser.add_argument('--schedule', default=[80000, 100000, 120000], nargs='+')
parser.add_argument('--momentum', default=0.9, type=float, help='momentum')
parser.add_argument('--weight_decay', default=5e-4, type=float, help='Weight decay for SGD')
parser.add_argument('--gamma', default=0.1, type=float, help='Gamma update for SGD')

# model params
# parser.add_argument('--jaccard_threshold', default=0.5, type=float, help='Min Jaccard index for matching')
# parser.add_argument('--voc_root', default=VOCroot, help='Location of VOC root directory')
parser.add_argument('--ssd_dim', default=512, type=int)
parser.add_argument('--prior_config', default='v2_512', type=str)
# parser.add_argument('--prior_config', default='v2_634', type=str)

# runtime and display
parser.add_argument('--num_workers', default=2, type=int, help='Number of workers used in dataloading')
# parser.add_argument('--cuda', default=True, type=str2bool, help='Use cuda to train model')
parser.add_argument('--visdom', default=False, type=str2bool, help='Use visdom to for loss visualization')
parser.add_argument('--port_id', default=8097, type=int)
parser.add_argument('--display_id', default=1, type=int)
parser.add_argument('--send_images_to_visdom', type=str2bool, default=False,
                    help='Sample a random image from each 10th batch, send it to visdom after augmentations step')

args = parser.parse_args()
args.debug = not args.deploy
args.phase = 'train'
# args.gpu_id = util._process(args.gpu_id)

args.save_folder = os.path.join('result', args.experiment_name, args.phase)
if args.resume:
    args.resume = os.path.join(args.save_folder, (args.resume + '.pth'))

if type(args.schedule[0]) == str:
    temp_ = args.schedule[0].split(',')
    schedule = list()
    for i in range(len(temp_)):
        schedule.append(int(temp_[i]))
    args.schedule = schedule

if not os.path.exists(args.save_folder):
    util.mkdirs(args.save_folder)

if torch.cuda.is_available():
    args.cuda = True
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    torch.set_default_tensor_type('torch.FloatTensor')

if args.debug:
    args.loss_freq, args.save_freq = 1, 5
else:
    args.loss_freq, args.save_freq = 50, 5000