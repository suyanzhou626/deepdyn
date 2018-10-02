"""
### author: Aashis Khanal
### sraashis@gmail.com
### date: 9/10/2018
"""
import os
import sys

try:
    BASE_PROJECT_DIR = '/home/ak/PycharmProjects/ature'
    sys.path.append(BASE_PROJECT_DIR)
    os.chdir(BASE_PROJECT_DIR)
except:
    BASE_PROJECT_DIR = '/home/akhanal1/ature'
    sys.path.append(BASE_PROJECT_DIR)
    os.chdir(BASE_PROJECT_DIR)

import os
import sys
import traceback

sys.path.append(BASE_PROJECT_DIR)
os.chdir(BASE_PROJECT_DIR)

import torch
import torch.optim as optim
from neuralnet.unet.model import UNet
from neuralnet.unet.unet_dataloader import PatchesGenerator
from neuralnet.unet.unet_trainer import UNetNNTrainer
import torchvision.transforms as transforms
from neuralnet.utils import auto_split as asp
import neuralnet.unet.runs  as rs

RUNS = [rs.WIDE0, rs.WIDE5, rs.WIDE10, rs.WIDE15, rs.WIDE20, rs.WIDE25,
        rs.STARE0, rs.STARE4, rs.STARE8, rs.STARE12, rs.STARE16,
        rs.VEVIO0, rs.VEVIO4, rs.VEVIO8, rs.VEVIO12]
torch.cuda.set_device(0)

if __name__ == "__main__":

    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.ToTensor()
    ])

    for R in RUNS:
        for k, folder in R['Dirs'].items():
            os.makedirs(folder, exist_ok=True)

        splits = asp.load_split_json(R.get(R.get('Params').get('checkpoint_file') + '.json'))

        model = UNet(R['Params']['num_channels'], R['Params']['num_classes'])
        optimizer = optim.Adam(model.parameters(), lr=R['Params']['learning_rate'])
        if R['Params']['distribute']:
            model = torch.nn.DataParallel(model)
            model.float()
            optimizer = optim.Adam(model.module.parameters(), lr=R['Params']['learning_rate'])

        try:
            drive_trainer = UNetNNTrainer(model=model, run_conf=R)

            if R.get('Params').get('mode') == 'train':
                train_loader = PatchesGenerator.get_loader(run_conf=R, images=splits['train'], transforms=transform,
                                                           mode='train')
                val_loader = PatchesGenerator.get_loader_per_img(run_conf=R, images=splits['validation'],
                                                                 mode='validation')
                drive_trainer.train(optimizer=optimizer, data_loader=train_loader, validation_loader=val_loader)

            drive_trainer.resume_from_checkpoint(parallel_trained=R.get('Params').get('parallel_trained'))
            test_loader = PatchesGenerator.get_loader_per_img(run_conf=R,
                                                              images=splits['test'], mode='test')

            log_file = os.path.join(R['Dirs']['logs'], R['Params']['checkpoint_file'] + '-TEST.csv')
            logger = drive_trainer.get_logger(log_file)
            drive_trainer.evaluate(data_loaders=test_loader, logger=logger, gen_images=True)
            logger.close()
        except Exception as e:
            traceback.print_exc()
