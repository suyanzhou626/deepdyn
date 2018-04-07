import os

from commons.segmentation import AtureTest
from commons.IMAGE import Image
import utils.img_utils as imgutil
import neuralnet.utils.data_utils as nndutil
os.chdir('/home/akhanal1/Spring2018/ature')
sep = os.sep

Dirs = {}

Dirs['data'] = 'data' + sep + 'DRIVE' + sep + 'training'

Dirs['images'] = Dirs['data'] + sep + 'images'
Dirs['mask'] = Dirs['data'] + sep + 'mask'
Dirs['truth'] = Dirs['data'] + sep + '1st_manual'
Dirs['segmented'] = Dirs['data'] + sep + 'drive_segmented'
Dirs['patches'] = Dirs['data'] + sep + 'patches'

for k, folder in Dirs.items():
    os.makedirs(folder, exist_ok=True)


def get_mask_file(file_name):
    return file_name.split('_')[0] + '_training_mask.gif'


def get_ground_truth_file(file_name):
    return file_name.split('_')[0] + '_manual1.gif'


params = {'sk_threshold': 60,
          'alpha': 7.5,
          'orig_contrib': 0.3,
          'seg_threshold': 24}

tester = AtureTest(out_dir=Dirs['segmented'])
tester.run_all(data_dir=Dirs['images'], mask_path=Dirs['mask'], gt_path=Dirs['truth'], save_images=True,
               params_combination=[params], fget_mask=get_mask_file, fget_gt=get_ground_truth_file)


# Generate patches
def get_segmented_file(file_name):
    return file_name + '_SEG.PNG'


for input_image in os.listdir(Dirs['images']):
    img_obj = Image()

    img_obj.load_file(data_dir=Dirs['images'], file_name=input_image)
    img_obj.load_mask(mask_dir=Dirs['mask'], fget_mask=get_mask_file, erode=True)
    img_obj.load_ground_truth(gt_dir=Dirs['truth'], fget_ground_truth=get_ground_truth_file)
    segmented_file = os.path.join(Dirs['segmented'], get_segmented_file(input_image))
    img_obj.res['segmented'] = imgutil.get_image_as_array(segmented_file, channels=1)

    img_obj.working_arr = img_obj.image_arr[:, :, 1]
    img_obj.working_arr = imgutil.whiten_image2d(img_obj.working_arr)
    nndutil.generate_patches(base_path=Dirs['patches'], img_obj=img_obj, k_size=31, save_images=False)