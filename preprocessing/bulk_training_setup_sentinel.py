# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 22:38:07 2019

@author: Daniel
"""
import numpy as np
import os, shutil, glob, random
from skimage.io import imsave, imread
import sys
sys.path.insert(0, '../training')
from aug_generators import aug_resize

source_path = r'../reprocessing\sentinel_raw'
dest_path = r"../reprocessing\sentinel_raw"

domains = sorted(os.listdir(source_path))
domains_count = len(domains)

augs = aug_resize(img_size=1024)
for domain in os.listdir(source_path):
	source_domain_path = os.path.join(source_path, domain)
	dest_domain_path = os.path.join(source_path, domain)
	print(domain)
	for file_name in os.listdir(source_domain_path):
		if '_mask' not in file_name:
			file_name_parts = file_name.split('_')
			file_name_base = file_name.split('.')[0]
			mask_file_name = file_name_base + '_mask.png'
			dest_raw_file_path = os.path.join(dest_domain_path, file_name)
			dest_mask_file_path = os.path.join(dest_domain_path, mask_file_name)
			source_file_path = os.path.join(source_domain_path, file_name)
			print(dest_raw_file_path, dest_mask_file_path)
		
			img = imread(source_file_path, as_gray=True)
			if img.dtype == np.uint8:
				img = img.astype(np.uint16) * 257
			elif img.dtype == np.float64:
				img = (img * 65535).astype(np.uint16)
				
			if img.shape[0] < 1024 or img.shape[1] < 1024:
				dat = augs(image=img)
				img_aug = dat['image'] #np.uint16 [0, 65535]
			else:
				img_aug = img
				
			imsave(dest_raw_file_path, img_aug)
			imsave(dest_mask_file_path, img_aug)