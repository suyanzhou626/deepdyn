"""
### author: Aashis Khanal
### sraashis@gmail.com
### date: 9/10/2018
"""

import os
import sys

import PIL.Image as IMG
import numpy as np
import torch
import torch.nn.functional as F

from neuralnet.utils.measurements import ScoreAccumulator


class NNTrainer:

    def __init__(self, run_conf=None, model=None):

        self.run_conf = run_conf
        self.log_dir = self.run_conf.get('Dirs').get('logs', 'net_logs')
        self.use_gpu = self.run_conf['Params'].get('use_gpu', False)
        self.epochs = self.run_conf.get('Params').get('epochs', 100)
        self.log_frequency = self.run_conf.get('Params').get('log_frequency', 10)
        self.validation_frequency = self.run_conf.get('Params').get('validation_frequency', 1)

        self.checkpoint_file = os.path.join(self.log_dir, self.run_conf.get('checkpoint_file'))
        self.temp_chk_file = os.path.join(self.log_dir, 'RUNNING' + self.run_conf.get('checkpoint_file'))
        self.log_file = os.path.join(self.log_dir, self.run_conf.get('checkpoint_file') + '-TRAIN.csv')

        if torch.cuda.is_available():
            self.device = torch.device("cuda" if self.use_gpu else "cpu")
        else:
            print('### GPU not found.')
            self.device = torch.device("cpu")

        self.model = model.to(self.device)

        self.checkpoint = {'epochs': 0, 'state': None, 'score': 0.0, 'model': 'EMPTY'}

    def train(self, optimizer=None, data_loader=None, validation_loader=None):

        if validation_loader is None:
            raise ValueError('Please provide validation loader.')

        logger = NNTrainer.get_logger(self.log_file, header='ID,TYPE,EPOCH,BATCH,PRECISION,RECALL,F1,ACCURACY,LOSS')
        print('Training...')
        for epoch in range(1, self.epochs + 1):
            self.model.train()
            score_acc = ScoreAccumulator()
            running_loss = 0.0
            self.adjust_learning_rate(optimizer=optimizer, epoch=epoch)
            for i, data in enumerate(data_loader, 1):
                inputs, labels = data['inputs'].to(self.device), data['labels'].long().to(self.device)

                optimizer.zero_grad()
                outputs = self.model(inputs)
                _, predicted = torch.max(outputs, 1)

                loss = F.nll_loss(outputs, labels)
                loss.backward()
                optimizer.step()

                current_loss = loss.item()
                running_loss += current_loss
                p, r, f1, a = score_acc.reset().add_tensor(labels, predicted).get_prf1a()
                if i % self.log_frequency == 0:
                    print('Epochs[%d/%d] Batch[%d/%d] loss:%.5f pre:%.3f rec:%.3f f1:%.3f acc:%.3f' %
                          (
                              epoch, self.epochs, i, data_loader.__len__(), running_loss / self.log_frequency, p, r, f1,
                              a))
                    running_loss = 0.0

                self.flush(logger, ','.join(str(x) for x in [0, 0, epoch, i, p, r, f1, a, current_loss]))

            if epoch % self.validation_frequency == 0:
                self.evaluate(data_loaders=validation_loader, logger=logger, gen_images=False)
        try:
            logger.close()
        except IOError:
            pass

    def evaluate(self, data_loaders=None, logger=None, gen_images=False):
        assert (logger is not None), 'Please Provide a logger'
        self.model.eval()

        print('\nEvaluating...')
        with torch.no_grad():
            eval_score = 0.0

            for loader in data_loaders:
                img_obj = loader.dataset.image_objects[0]
                segmented_img = torch.cuda.LongTensor(img_obj.working_arr.shape[0],
                                                      img_obj.working_arr.shape[1]).fill_(0).to(self.device)
                gt = torch.LongTensor(img_obj.ground_truth).to(self.device)

                for i, data in enumerate(loader, 1):
                    inputs, labels = data['inputs'].float().to(self.device), data['labels'].float().to(self.device)
                    clip_ix = data['clip_ix'].int().to(self.device)

                    outputs = self.model(inputs)
                    _, predicted = torch.max(outputs, 1)

                    for j in range(predicted.shape[0]):
                        p, q, r, s = clip_ix[j]
                        segmented_img[p:q, r:s] += predicted[j]
                    print('Batch: ', i, end='\r')

                segmented_img[segmented_img > 0] = 255
                # segmented_img[img_obj.mask == 0] = 0

                img_score = ScoreAccumulator()

                if gen_images:
                    segmented_img = segmented_img.cpu().numpy()
                    img_score.add_array(img_obj.ground_truth, segmented_img)
                    IMG.fromarray(np.array(segmented_img, dtype=np.uint8)).save(
                        os.path.join(self.log_dir, img_obj.file_name.split('.')[0] + '.png'))
                else:
                    img_score.add_tensor(segmented_img, gt)
                    eval_score += img_score.get_prf1a()[2]

                prf1a = img_score.get_prf1a()
                print(img_obj.file_name, ' PRF1A', prf1a)
                self.flush(logger, ','.join(str(x) for x in [img_obj.file_name, 1, 0, 0] + prf1a))

        self._save_if_better(score=eval_score / len(data_loaders))

    def resume_from_checkpoint(self, parallel_trained=False):
        try:
            self.checkpoint = torch.load(self.checkpoint_file)
            if parallel_trained:
                from collections import OrderedDict
                new_state_dict = OrderedDict()
                for k, v in self.checkpoint['state'].items():
                    name = k[7:]  # remove `module.`
                    new_state_dict[name] = v
                # load params
                self.model.load_state_dict(new_state_dict)
            else:
                self.model.load_state_dict(self.checkpoint['state'])
            print('RESUMED FROM CHECKPOINT: ' + self.checkpoint_file)
        except Exception as e:
            print('ERROR: ' + str(e))

    def _save_if_better(self, score=None):
        score = round(score, 5)
        current_epoch = self.checkpoint['epochs'] + self.validation_frequency
        current_chk = {'state': self.model.state_dict(),
                       'epochs': current_epoch,
                       'score': score,
                       'model': str(self.model)}

        # Save a running version of checkpoint with a different name
        torch.save(current_chk, self.temp_chk_file)

        if score > self.checkpoint['score']:
            torch.save(current_chk, self.checkpoint_file)
            print('Score improved: ',
                  str(self.checkpoint['score']) + ' to ' + str(score) + ' BEST CHECKPOINT SAVED')
            self.checkpoint = current_chk
        else:
            print('Score did not improve:' + str(score) + ' BEST: ' + str(self.checkpoint['score']))

    @staticmethod
    def get_logger(log_file=None, header=''):

        if os.path.isfile(log_file):
            print('### CRITICAL!!! ' + log_file + '" already exists. OVERRIDE [Y/N]?')
            ui = input()
            if ui == 'N' or ui == 'n':
                sys.exit(1)

        file = open(log_file, 'w')
        NNTrainer.flush(file, header)
        return file

    @staticmethod
    def flush(logger, msg):
        if logger is not None:
            logger.write(msg + '\n')
            logger.flush()
        pass

    @staticmethod
    def adjust_learning_rate(optimizer, epoch):
        if epoch % 40 == 0:
            for param_group in optimizer.param_groups:
                if param_group['lr'] >= 1e-5:
                    param_group['lr'] = param_group['lr'] * 0.5
