from __future__ import print_function
import torch.optim as optim
import torch.utils.data as data
from data.create_dset import create_dataset
import torch.backends.cudnn as cudnn
import torch.nn as nn
from layers.modules.capsule import CapsNet
from layers.modules.cap_layer import MarginLoss, SpreadLoss
from layers.modules.cifar_train_val import *
from utils.visualizer import Visualizer
from utils.util import *
from option.train_opt import args   # for cifar we also has test here

# ==============================
args.experiment_name = 'cifar_base_104_KL_new'
args.cap_model = 'v0'
args.non_target_j = True
args.see_all_sample = True
args.which_batch_idx = 67
test_model_list = [1, 20, 80, 200, 280]
# only makes sense when 'see_all_sample' is false
args.port = 2000
# ==============================
args.show_freq = 5
args.draw_hist = True
args.test_only = True
args.save_folder = os.path.join('result', args.experiment_name, args.phase)
if args.see_all_sample:
    args.which_batch_idx = -1
args = show_jot_opt(args)
vis = Visualizer(args)

test_loader = data.DataLoader(create_dataset(args, 'test'), args.test_batch,
                              num_workers=args.num_workers, shuffle=False)
model = CapsNet(num_classes=test_loader.dataset.num_classes, opts=args)
print_log(model, args.file_name)
# set loss
if args.model_cifar == 'capsule':
    if args.use_CE_loss:
        criterion = nn.CrossEntropyLoss()
    elif args.use_spread_loss:
        criterion = SpreadLoss(args, fix_m=args.fix_m,
                               num_classes=test_loader.dataset.num_classes)
    else:
        # default loss
        criterion = MarginLoss(num_classes=test_loader.dataset.num_classes)
elif args.model_cifar == 'resnet':
    criterion = nn.CrossEntropyLoss()
if args.use_cuda:
    criterion, model = criterion.cuda(), model.cuda()
cudnn.benchmark = True


for _, i in enumerate(test_model_list):
    model_file = \
        os.path.join(args.save_folder, 'epoch_{:d}.pth'.format(i))
    print('loading weights of model [{:s}]'.format(os.path.basename(model_file)))
    try:
        model = load_weights(model_file, model)
    except AssertionError:
        print('warning: you may run on cpu; model weights initialized instead of loading models')
    args.cifar_model = model_file
    info = test(test_loader, model, criterion, args, vis)
    print('test acc is {:.4f}'.format(info['test_acc']))








