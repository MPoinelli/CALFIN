# -*- coding: utf-8 -*-
"""
Created on Thu May 30 09:28:22 2019

@author: Daniel
"""
import numpy as np
import os, glob, cv2, shutil
import matplotlib.pyplot as plt
from scipy.misc import imresize
from scipy.ndimage import distance_transform_edt
from redistribute_points import redistribute_points
from skimage.morphology import skeletonize
import skimage
import meshcut
from scipy import ndimage
from ordered_line_from_unordered_points import ordered_line_from_unordered_points, ordered_line_from_unordered_points_tree
from PIL import Image
from cv2 import VideoWriter, VideoWriter_fourcc, imread, resize
from collections import defaultdict
from osgeo import gdal, ogr, osr
		
from shapely.geometry import mapping, Polygon
import fiona
from fiona.crs import from_epsg
plt.ioff()

steps = ['1', '2', '3', '4']
steps = ['1']
steps = ['2']
steps = ['3']
#steps = ['4']
#steps = ['1', '2']
steps = ['1', '2', '3']
#steps = ['A']
#steps = ['production']

"""Load domain to process"""
def landsat_sort(file_path):
	"""Sorting key function derives date from landsat file path."""
#	print(file_path)
	return file_path.split(os.path.sep)[-1].split('_')[3]

def get_paths(root, domain, suffix):
	"""Gets a sorted list of file paths from the specified root directory, subdirectory, and file name regex/glob pattern."""
	paths = glob.glob(os.path.join(root, domain, '*' + suffix + '.png'))
#	paths.sort(key=landsat_sort)
	return paths

def step_1(root, domain):
	"""Gets the sorted lists of files for the specified root and subdirectory."""
	raw_paths = get_paths(root, domain, '[0-9]')
	mask_paths =  get_paths(root, domain, '_mask')
	return raw_paths, mask_paths

if '1' in steps:
	#For testing - performs step 1 with default parameters.
	root = r'D:\Daniel\Documents\Github\CALFIN Repo\training\data'
	domain = 'train'
	raw_paths, mask_paths = step_1(root, domain)
	


"""Front Extraction"""
def extract_front(raw_img, mask_img):
	raw_rgb_img = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2RGB)
	cimg, contours, hierarchy = cv2.findContours(mask_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	front = contours[0]
	cv2.drawContours(raw_rgb_img, [front], -1, (0,255,0), 3)
	return raw_rgb_img, contours

def extract_front_indicators(raw_img, mask_img, index, resolution):
	"""Extracts an ordered polyline from the processed mask. Also returns an overlay of the extracted polyline and the raw image. Draws to the indexed figure and specified resolution."""
	width = resolution[0]
	height = resolution[1]
	minimum_points = 4
	
	#Extract known masks
	raw_rgb_img = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2RGB)
	#edges = cv2.Canny(mask_img,100,200)
	edge_bianry = np.where(mask_img > 127, 1, 0)
	skeleton = skeletonize(edge_bianry)
	front_pixels = np.nonzero(skeleton)
	
	#Require a minimum number of points
	if len(front_pixels[0]) < minimum_points:
		return None
	
	#Prepare figure for direct image output/saving
	dpi = 80
	fig = plt.figure(index, figsize=(width/dpi, height/dpi), dpi=dpi)
	plt.clf()
	plt.subplots_adjust(top = 1, bottom = 0, right = 1, left = 0, 
				hspace = 0, wspace = 0)
	plt.imshow(raw_rgb_img)
	ax = plt.gca()
	ax.axis('tight')
	ax.axis('off')
	ax.set_xlim(0.0, width)
	ax.set_ylim(height, 0.0)
#	plt.show()
	
	#Perform mask to polyline extraction.
	front_line = np.array(ordered_line_from_unordered_points_tree(front_pixels, raw_img.shape, minimum_points))
	number_of_points = front_line.shape[1]
	front_normals = np.zeros((2, number_of_points))
	
	#Require a minimum number of points
	if len(front_line[0]) < minimum_points:
		return None
	
	#Calculate normals for endpoints.
	i = 0
	p1 = front_line[:, i]
	p2 = front_line[:, i + 1]
	d21 = p2 - p1
	n21 = np.array([-d21[1], d21[0]])
	n1 = n21
	n1 = n1 / np.linalg.norm(n1)
	front_normals[:,i] = n1
	
	i = number_of_points - 1
	p0 = front_line[:, i - 1]
	p1 = front_line[:, i]
	d10 = p1 - p0
	n10 = np.array([-d10[1], d10[0]])
	n1 = n10
	n1 = n1 / np.linalg.norm(n1)
	front_normals[:,i] = n1
	
	#Calculate normals for all other points.
	for i in range(1, number_of_points - 1):
		p0 = front_line[:, i - 1]
		p1 = front_line[:, i]
		p2 = front_line[:, i + 1]
		d10 = p1 - p0
		d21 = p2 - p1
		n10 = np.array([d10[1], -d10[0]])
		n21 = np.array([d21[1], -d21[0]])
		n1 = n10 + n21
		n1 = n1 / np.linalg.norm(n1)
		front_normals[:,i] = n1
	
	#Draw normals over raw image.
#		raw_rgb_img = np.zeros((512, 512, 3)) + 0.5
#		for i in range(len(front_line[0])):
#			raw_rgb_img[front_line[0, i], front_line[1, i]] = [front_normals[0,i] / 2 + 0.5, front_normals[1,i] / 2 + 0.5, 0.5]
	
	#Save figure as image matrix.
	fig.canvas.draw()
	data = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8, sep='')
	overlay = data.reshape(fig.canvas.get_width_height()[::-1] + (3,))

	return overlay, front_line, front_normals


def step_2(raw_paths, mask_paths, reprocessing_path, source_root_path):
	"""Extracts image overlays, polyline fronts, polyline normals, and valid return raw paths for all images in paths."""
	#base_date = 
	overlays = []
	fronts_lines = []
	fronts_normals = []
	processed_paths = []
	
	#Determine resolution
	img_sizes = []
	for i in range(0, len(mask_paths)):
		img = Image.open(raw_paths[i])
		img_sizes.append(img.size)
	img_sizes = np.array(img_sizes)
	resolution = np.median(img_sizes, axis=0)
	width, height = 512, 512
	resolution = np.array([width, height])
	
	for i in range(0, len(mask_paths)):
#	for i in range(0, 100):
		raw_path = raw_paths[i]
		mask_path = mask_paths[i]
		print(i, mask_path)
		
		#Work around for Unicode characters not being read by cv2 imread (works for skimage imageio)
		img_stream = open(raw_path, "rb")
		img_bytes_array = bytearray(img_stream.read())
		img_np_bytes_array = np.asarray(img_bytes_array, dtype=np.uint8)
		raw_img_uint16 = cv2.imdecode(img_np_bytes_array, cv2.IMREAD_UNCHANGED)[:,:,1]
		img_stream.close()

		mask_stream = open(mask_path, "rb")
		mask_bytes_array = bytearray(mask_stream.read())
		mask_np_bytes_array = np.asarray(mask_bytes_array, dtype=np.uint8)
		mask_img_uint16 = cv2.imdecode(mask_np_bytes_array, cv2.IMREAD_UNCHANGED)
		mask_stream.close()
		
		#Convert greyscale to RGB greyscale
		img_max = raw_img_uint16.max()
		img_min = raw_img_uint16.min()
		img_range = img_max - img_min
		mask_max = mask_img_uint16.max()
		#Might want to experiemnt with no rounding?
		if (img_max != 0.0 and img_range > 255.0):
			img_uint8 = (raw_img_uint16 / img_max * 255.0).astype(np.float32) #np.float32 [0.0, 255.0] Keep range 0-255 to conform to imagenet standards, but keep dtype float32 to keep precision
		else:
			img_uint8 = raw_img_uint16.astype(np.uint8)
		if (mask_max != 0.0):
			mask_uint8 = np.floor(mask_img_uint16 / mask_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		else:
			mask_uint8 = mask_img_uint16.astype(np.uint8)
		
		raw_img = np.array(Image.fromarray(img_uint8).resize((width, height), Image.BICUBIC)).astype('uint8')
		mask_img = np.array(Image.fromarray(mask_uint8).resize((width, height), Image.BICUBIC)).astype('uint8')
		
#		raw_img = np.array(Image.fromarray(cv2.imread(raw_path, 0)).resize((width, height), Image.BICUBIC)).astype('uint8')
#		mask_img = np.array(Image.fromarray(cv2.imread(mask_path, 0)).resize((width, height), Image.BICUBIC)).astype('uint8')
		mask_edge = cv2.Canny(mask_img, 250, 255 * 2) #thresholds = Use diagonals to detect strong edges, then connect anything with at least a single edge
		result = extract_front_indicators(raw_img, mask_edge, i, resolution)

		if result != None:
			overlay = result[0]
			front_lines = result[1]
			front_normals = result[2]
			overlays.append(overlay)
			fronts_lines.append(front_lines)
			fronts_normals.append(front_normals)
			processed_paths.append(raw_path)
		else:
			name_split = raw_path.split('\\')[-1]
			domain = name_split.split('_')[0]
			basename = os.path.splitext(name_split)[0]
			raw_name = basename + '.png'
			mask_name = basename + '_mask.png'
			source_path = os.path.join(source_root_path)
			domain_path = os.path.join(reprocessing_path, domain)
			if not os.path.exists(domain_path):
				os.mkdir(domain_path)
			shutil.copy2(os.path.join(source_path, raw_name), os.path.join(domain_path, raw_name))
			shutil.copy2(os.path.join(source_path, raw_name), os.path.join(domain_path, mask_name))
	return overlays, fronts_lines, fronts_normals, processed_paths

if '2' in steps:
	#For testing - performs step 2 with default parameters.
	root_path = r'D:\Daniel\Pictures\CALFIN Imagery\landsat_preds'
	output_path = r'D:\Daniel\Documents\Github\CALFIN Repo\postprocessing\videos'
	reprocessing_path = r'D:\Daniel\Documents\Github\CALFIN Repo\reprocessing\no_fronts'
	source_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\training\data\train_original'
	overlays, fronts_lines, fronts_normals, processed_paths = step_2(raw_paths, mask_paths, reprocessing_path, source_root_path)

"""Endpoint determination and Shapefile output"""
def step_3(fronts_lines, tif_path, reprocessing_path, source_root_path, dest_root_path):
	"""Determines endpoints by finding the median"""
	start_points = []
	end_points = []
	for i in range(len(fronts_lines)):
		start_points.append(fronts_lines[i][:,0])
		end_points.append(fronts_lines[i][:,-1])
	start_points = np.array(start_points)
	end_points = np.array(end_points)
	median_start_point = np.median(start_points, axis=0)
	median_end_point = np.median(end_points, axis=0)
	
	#Reprocess images that do not conform
	for i in range(len(start_points)):
#		start_diff = np.linalg.norm(median_start_point - start_points[i])
#		end_diff = np.linalg.norm(median_end_point - end_points[i])
#		if start_diff > 10 or end_diff > 10:
#			raw_path = processed_paths[i]
#			name_split = raw_path.split('\\')[-1]
#			domain = name_split.split('_')[0]
#			basename = os.path.splitext(name_split)[0]
#			raw_name = basename + '.png'
#			mask_name = basename + '_mask.png'
#			source_path = os.path.join(source_root_path, raw_name)
#			domain_path = os.path.join(reprocessing_path, domain)
#			if not os.path.exists(domain_path):
#				os.mkdir(domain_path)
#			shutil.copy2(source_path, os.path.join(domain_path, raw_name))
#			shutil.copy2(source_path, os.path.join(domain_path, mask_name))
#		else:
		#write out shp file
		raw_path = processed_paths[i]
		file_name = raw_path.split('\\')[-1]
		file_name_parts = file_name.split('_')
		if len(file_name_parts) < 3:
			continue
		domain = file_name_parts[0]
		date =  file_name_parts[3]
		year = date.split('-')[0]
		basename = os.path.splitext(file_name)[0]
		raw_name = basename + '.tif'
		mask_name = basename + '_mask.png'
		shp_name = basename + '.shp'
		tif_name = basename + '.tif'
		year = date.split('-')[0]
		source_path = os.path.join(source_root_path, raw_name)
		source_tif_path = os.path.join(tif_path, domain, year, raw_name)
		
		dest_shp_folder = os.path.join(dest_root_path, 'shp', domain)
		dest_tif_folder = os.path.join(dest_root_path, 'tif', domain)
		dest_all_folder = os.path.join(dest_root_path, 'all', domain)
		dest_shp_year_folder = os.path.join(dest_shp_folder, year)
		dest_tif_year_folder = os.path.join(dest_tif_folder, year)
		
		if not os.path.exists(source_tif_path):
			continue
#		if not os.path.exists(dest_shp_folder):
#			os.mkdir(dest_shp_folder)
#		if not os.path.exists(dest_tif_folder):
#			os.mkdir(dest_tif_folder)
		if not os.path.exists(dest_all_folder):
			os.mkdir(dest_all_folder)
#		if not os.path.exists(dest_shp_year_folder):
#			os.mkdir(dest_shp_year_folder)
#		if not os.path.exists(dest_tif_year_folder):
#			os.mkdir(dest_tif_year_folder)
				
		dest_shp_path = os.path.join(dest_shp_year_folder, shp_name)
		dest_tif_path = os.path.join(dest_tif_year_folder, shp_name)
		dest_shp_all_path = os.path.join(dest_all_folder, shp_name)
		dest_tif_all_path = os.path.join(dest_all_folder, tif_name)

		
		# Here's an example Shapely geometry
		vertex_list = list(zip(fronts_lines[i][1], fronts_lines[i][0]))
		vertex_list.append(vertex_list[0])
		vertex_list = np.array(vertex_list)
		vertex_list_normalized_f32 = vertex_list.astype(np.float32) / 512.0
		
		# Load geotiff and get domain layer/bounding box of area to mask
		geotiff = gdal.Open(source_tif_path)
		print(source_tif_path)
		prj = geotiff.GetProjection()
		srs = osr.SpatialReference(wkt=prj)
		rasterCRS = srs.GetAttrValue("PROJCS|AUTHORITY", 1)
		if (rasterCRS is None):
			rasterCRS = srs.GetAttrValue("AUTHORITY", 1)
		rasterCRS = int(rasterCRS)
		
		#Get bounds
		geoTransform = geotiff.GetGeoTransform()
		xMin = geoTransform[0]
		yMax = geoTransform[3]
		xMax = xMin + geoTransform[1] * geotiff.RasterXSize
		yMin = yMax + geoTransform[5] * geotiff.RasterYSize
		
		#Transform vertices
		top_left = np.array([xMin, yMax])
		scale = np.array([xMax - xMin, yMin - yMax])
		vertex_list_transformed_f32 = (vertex_list_normalized_f32 * scale) + top_left
		poly = Polygon(vertex_list_transformed_f32)
		
		# Define a polygon feature geometry with one attribute
		schema = {
			'geometry': 'Polygon',
			'properties': {'id': 'int'},
		}
		
		# Write a new Shapefile
		with fiona.open(
				dest_shp_all_path,
				'w',
				driver='ESRI Shapefile',
				crs=from_epsg(rasterCRS),
				schema=schema) as c:
			
			## If there are multiple geometries, put the "for" loop here
			c.write({
				'geometry': mapping(poly),
				'properties': {'id': 0},
			})
			shutil.copy2(source_tif_path, dest_tif_all_path)
	
	return median_start_point, median_end_point

if '3' in steps:
	tif_path = r'D:\Daniel\Documents\Github\CALFIN Repo\preprocessing\CalvingFronts\tif'
	output_path = r'D:\Daniel\Documents\Github\CALFIN Repo\postprocessing\videos'
	reprocessing_path = r'D:\Daniel\Documents\Github\CALFIN Repo\reprocessing\no_fronts'
	source_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\training\data\train_original'
	dest_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\postprocessing\CalvingFronts'
	#For testing - performs step 3 with default parameters.
	median_start_point, median_end_point = step_3(fronts_lines, tif_path, reprocessing_path, source_root_path, dest_root_path)
	

"""Visualize/Movie output"""
def get_date(image_path):
	"""Takes in a Landsat image path, and returns date string as well as individual year, month, and day strings."""
	name_split = image_path.split('\\')[-1].split('_')
	date = name_split[3]
	date_parts = date.split('-')
	year = date_parts[0]
	month = date_parts[1]
	day = date_parts[2]
	return date, year, month, day

def make_video(images, images_paths, output_path, fps=1.0, size=None, is_color=True, format='MJPG'):
	"""
	Create a video from a list of images.

	@param	  outvid	 	output video
	@param	  image_paths	list of images to use in the video
	@param	  fps		 	frame per second
	@param	  size			size of each frame
	@param	  is_color		color
	@param	  format	 	see http://www.fourcc.org/codecs.php
	@return					see http://opencv-python-tutroals.readthedocs.org/en/latest/py_tutorials/py_gui/py_video_display/py_video_display.html

	The function relies on http://opencv-python-tutroals.readthedocs.org/en/latest/.
	By default, the video will have the size of the first image.
	It will resize every image to this size before adding them to the video.
	"""
	
	video_name = output_path + '.avi'
	fourcc = VideoWriter_fourcc(*'MJPG')
	vid = None
	for i in range(len(images_paths)):
		image_path = images_paths[i]
		img = images[i]
		if vid is None:
			if size is None:
				size = img.shape[1], img.shape[0]
			vid = VideoWriter(video_name, fourcc, float(fps), size, is_color)
		if size[0] != img.shape[1] or size[1] != img.shape[0]:
			img = resize(img, size)
		
		widthScale = img.shape[0] / 500 #(font is scaled for Upernavik, which is 500 pixels wide)
		heightScale = img.shape[1] / 500 #(font is scaled for Upernavik, which is 500 pixels wide)
		bottomLeftCornerOfText = (4, img.shape[1] - int(34 * heightScale))
		font = cv2.FONT_HERSHEY_SIMPLEX
		fontScale = 1 * widthScale
		fontColor = (0, 192, 216)
		fontColorBorder = (0, 0, 0)
		lineType = 2
		thickness = 2
		thicknessBorder = 8
		
		date, year, month, day = get_date(image_path)
				
		#text_width, text_height = cv2.getTextSize(date, font, fontScale, lineType)[0]
		cv2.putText(img, date, bottomLeftCornerOfText, font, fontScale, fontColorBorder, thickness=thicknessBorder, lineType=lineType)
		cv2.putText(img, date, bottomLeftCornerOfText, font, fontScale, fontColor, thickness=thickness, lineType=lineType)
		img = cv2.cvtColor(img,cv2.COLOR_RGB2BGR)
		vid.write(img)
	vid.release()
	return

def make_calendar(processed_paths):
	"""Generates year/month bins where measurements exist for given domain."""
	max_date, max_year, max_month, max_day = get_date(processed_paths[-1])
	min_year = 1972 #Landsat start
	max_year = int(max_year)
	year_range = max_year - min_year + 1
	yearly_bins = np.zeros((year_range, 1))
	monthly_bins = np.zeros((year_range, 12))
	
	#Populate year/month bins
	for i in range(len(processed_paths)):
		date, year, month, day = get_date(processed_paths[i])
		yearly_bins[int(year) - min_year, 0] += 1
		monthly_bins[int(year) - min_year, int(month)] += 1
			
	return yearly_bins, monthly_bins

def step_4(overlays, processed_paths, output_path, name):
	file_path = os.path.join(output_path, name)
	yearly_bins, monthly_bins = make_calendar(processed_paths)
	make_video(overlays, processed_paths, file_path, fps=1.0)
	return yearly_bins, monthly_bins

if '4' in steps:
	#For testing - performs step 4 with default parameters.
	output_path = '.'
	name = "Upernavik-NE"
	yearly_bins, monthly_bins = step_4(overlays, processed_paths, output_path, name)
	
	
"""Perform steps 1-4 for all domains"""
def save_domain(domain, raw_paths, mask_paths, overlays, fronts_lines, fronts_normals, processed_paths, yearly_bins, monthly_bins):
	"""Saves all domain specific global variables to npz file."""
	np.savez_compressed(domain + '.npz', 
	   raw_paths=raw_paths, 
	   mask_paths=mask_paths, 
	   overlays=overlays, 
	   fronts_lines=fronts_lines, 
	   fronts_normals=fronts_normals, 
	   processed_paths=processed_paths,
	   yearly_bins=yearly_bins,
	   monthly_bins=monthly_bins)

def load_domain(domain):
	"""Loads all domain specific global variables from npz file."""
	data = np.load(domain + '.npz')
	raw_paths = data['raw_paths'] 
	mask_paths = data['mask_paths'] 
	overlays = data['overlays'] 
	fronts_lines = data['fronts_lines'] 
	fronts_normals = data['fronts_normals'] 
	processed_paths = data['processed_paths']
	yearly_bins = data['yearly_bins']
	monthly_bins = data['monthly_bins']

if 'A' in steps:
	#For testing - performs all steps with default parameters.
	root_path = r'D:\Daniel\Pictures\CALFIN Imagery\landsat_preds'
	output_path = r'D:\Daniel\Documents\Github\CALFIN Repo\postprocessing\videos'
	reprocessing_path = r'D:\Daniel\Documents\Github\CALFIN Repo\reprocessing\images_full'
	source_root_path = r'D:\Daniel\Pictures\CALFIN Imagery\test_full'
	yearly_bins_all = dict()
	monthly_bins_all = dict()
	for domain in os.listdir(root_path):
		try:
			raw_paths, mask_paths = step_1(root_path, domain)
			overlays, fronts_lines, fronts_normals, processed_paths = step_2(raw_paths, mask_paths, reprocessing_path, source_root_path)
			median_start_point, median_end_point = step_3(fronts_lines, processed_paths, reprocessing_path, source_root_path)
			yearly_bins, monthly_bins = step_4(overlays, processed_paths, output_path, domain)
			yearly_bins_all[domain] = yearly_bins
			monthly_bins_all[domain] = monthly_bins
#			save_domain(domain, raw_paths, mask_paths, overlays, fronts_lines, fronts_normals, processed_paths, yearly_bins, monthly_bins)
#			break
		except Exception as e:
			print('Error with domain:', domain, '-', e)
	np.savez_compressed('time-bins.npz', yearly_bins_all=yearly_bins_all, monthly_bins_all=monthly_bins_all)
	#automatically save all images that don't have detections, and create masks

if 'production' in steps:
	preds_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\processing\landsat_preds_core'
	masks_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\training\data\validation'
	reprocessing_path = r'D:\Daniel\Documents\Github\CALFIN Repo\reprocessing\production'
	
	
	raw_paths = glob.glob(masks_root_path + '/*[0-9].png')
#	mask_paths = glob.glob(masks_root_path + '/*_mask.png')
#	pred_paths = glob.glob(preds_root_path + '/*_pred.png')
#	for i in range(0, 25):
	mean_errors = defaultdict(list)
	for i in range(len(raw_paths)):
		raw_path = raw_paths[i]
#		mask_path = mask_paths[i]
#		pred_path = pred_paths[i]
		
		image_name = raw_path.split(os.path.sep)[-1].split('.')[0]
		image_name_parts = image_name.split('_')
		domain = image_name_parts[0]
		band = image_name_parts[-1]
		mask_name = image_name + '_mask.png'
		pred_name = domain + '\\' + image_name + '_pred.png'
		mask_path = os.path.join(masks_root_path, mask_name)
		pred_path = os.path.join(preds_root_path, pred_name)
		
		if not os.path.exists(pred_path):
			continue
		
		img_uint16 = skimage.io.imread(raw_path, as_gray=True) #np.uint16 [0, 65535]
		mask_uint16 = skimage.io.imread(mask_path, as_gray=True) #np.uint16 [0, 65535]
		pred_uint8 = skimage.io.imread(pred_path, as_gray=True) #np.uint8 [0, 255]
		
		resolution = pred_uint8.shape
		resolution_original = mask_uint16.shape
		img_size = resolution[0]
		img_f64 = skimage.transform.resize(img_uint16, resolution, preserve_range=True)  #np.float64 [0.0, 65535.0]
		mask_f64 = skimage.transform.resize(mask_uint16, resolution, order=0, preserve_range=True) #np.float64 [0.0, 65535.0]
		pred_f64 = skimage.transform.resize(pred_uint8, resolution, order=0, preserve_range=True) #np.float64 [0.0, 255.0]
	
		#Convert greyscale to RGB greyscale
		img_max = img_f64.max()
		mask_max = mask_f64.max()
		pred_max = pred_f64.max()
		if (img_max != 0.0):
			img_uint8 = np.round(img_f64 / img_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		if (mask_max != 0.0):
			mask_uint8 = np.floor(mask_f64 / mask_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		if (pred_max != 0.0 and pred_max != 255.0):
			pred_uint8 = np.floor(pred_f64 / pred_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		
		#Calculate edge from mask and dilate.
		kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
		mask_edge = cv2.Canny(mask_uint8, 250, 255 * 2) #thresholds = Use diagonals to detect strong edges, then connect anything with at least a single edge
		mask_edge = cv2.dilate(mask_edge.astype('float64'), kernel, iterations = 1)
		
		result_mask = extract_front_indicators(img_uint8, mask_edge, i, resolution)
		result_pred = extract_front_indicators(img_uint8, pred_uint8, i, resolution)
		
		if result_pred is None or result_mask is None:
			#Save to reprocessing
#			print(raw_path, 'mean distance from front: NaN - unable to extract front')
			continue
		
		mask_test = np.zeros(resolution)
		pred_test = np.zeros(resolution)
		
		front_line_mask = result_mask[1]
		front_line_pred = result_pred[1]
		front_contour_mask = []
		front_contour_pred = []
		for j in range(len(front_line_mask[0])):
			front_contour_mask.append([front_line_mask[0][j], front_line_mask[1][j]])
		for j in range(len(front_line_pred[0])):
			front_contour_pred.append([front_line_pred[0][j], front_line_pred[1][j]])
		

				
		front_contour_mask = np.array([front_contour_mask], dtype=np.int32)
		cv2.fillPoly(mask_test, front_contour_mask, 255)
#		plt.figure(i * 2)
#		plt.clf()
#		plt.imshow(mask_test)
#		plt.show()
#		return
		front_contour_pred = np.array([front_contour_pred], dtype=np.int32)
		cv2.fillPoly(pred_test, front_contour_pred, 255)
#		plt.figure(i * 2 + 1)
#		plt.clf()
#		plt.imshow(pred_test)
#		plt.show()
		
		intersection = np.logical_xor(mask_test, pred_test)
		line_length = cv2.arcLength(front_contour_mask, False)
		error_area = np.sum(intersection)
		mean_error_per_unit = error_area / line_length
		
		x_scale = resolution_original[0] / resolution[0]
		y_scale = resolution_original[1] / resolution[1]
		norm_scale = np.sqrt(x_scale * x_scale + y_scale * y_scale)
		landsat_resolution = 30
		if band == 'B7':
			landsat_resolution = 60
		
		mean_error_per_meter = mean_error_per_unit * norm_scale * landsat_resolution
		mean_errors[domain].append(mean_error_per_meter)
#		print(raw_path, 'mean distance from front:', str(mean_error_per_meter) + 'm') 
#		raise Exception()
#		img_f64 = resize(img_uint16, (img_size, img_size), preserve_range=True)  #np.float64 [0.0, 65535.0]
#		mask_f64 = resize(mask_uint16, (img_size, img_size), order=0, preserve_range=True) #np.float64 [0.0, 65535.0]
#	
	for domain, error_array in mean_errors.items():
		print(domain, 'mean distance from front:', str(np.mean(error_array)) + 'm', 'median:', str(np.median(error_array)) + 'm')
		
if 'production' in steps:
	preds_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\processing\landsat_preds_core'
	masks_root_path = r'D:\Daniel\Documents\Github\CALFIN Repo\training\data\all'
	reprocessing_path = r'D:\Daniel\Documents\Github\CALFIN Repo\reprocessing\production'
	
	
	raw_paths = glob.glob(masks_root_path + '/*[0-9].png')
#	mask_paths = glob.glob(masks_root_path + '/*_mask.png')
#	pred_paths = glob.glob(preds_root_path + '/*_pred.png')
#	for i in range(0, 25):
	mean_errors = defaultdict(list)
	for i in range(len(raw_paths)):
		raw_path = raw_paths[i]
#		mask_path = mask_paths[i]
#		pred_path = pred_paths[i]
		
		image_name = raw_path.split(os.path.sep)[-1].split('.')[0]
		image_name_parts = image_name.split('_')
		domain = image_name_parts[0]
		band = image_name_parts[-1]
		mask_name = image_name + '_mask.png'
		pred_name = domain + '\\' + image_name + '_pred.png'
		mask_path = os.path.join(masks_root_path, mask_name)
		pred_path = os.path.join(preds_root_path, pred_name)
		
		if not os.path.exists(pred_path):
			continue
		
		img_uint16 = skimage.io.imread(raw_path, as_gray=True) #np.uint16 [0, 65535]
		mask_uint16 = skimage.io.imread(mask_path, as_gray=True) #np.uint16 [0, 65535]
		pred_uint8 = skimage.io.imread(pred_path, as_gray=True) #np.uint8 [0, 255]
		
		resolution = pred_uint8.shape
		resolution_original = mask_uint16.shape
		img_size = resolution[0]
		img_f64 = skimage.transform.resize(img_uint16, resolution, preserve_range=True)  #np.float64 [0.0, 65535.0]
		mask_f64 = skimage.transform.resize(mask_uint16, resolution, order=0, preserve_range=True) #np.float64 [0.0, 65535.0]
		pred_f64 = skimage.transform.resize(pred_uint8, resolution, order=0, preserve_range=True) #np.float64 [0.0, 255.0]
	
		#Convert greyscale to RGB greyscale
		img_max = img_f64.max()
		mask_max = mask_f64.max()
		pred_max = pred_f64.max()
		if (img_max != 0.0):
			img_uint8 = np.round(img_f64 / img_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		if (mask_max != 0.0):
			mask_uint8 = np.floor(mask_f64 / mask_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		if (pred_max != 0.0 and pred_max != 255.0):
			pred_uint8 = np.floor(pred_f64 / pred_max * 255.0).astype(np.uint8) #np.uint8 [0, 255]
		
		#Calculate edge from mask and dilate.
		kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
		mask_edge = cv2.Canny(mask_uint8, 250, 255 * 2) #thresholds = Use diagonals to detect strong edges, then connect anything with at least a single edge
		mask_edge = cv2.dilate(mask_edge.astype('float64'), kernel, iterations = 1)
		
		result_mask = extract_front_indicators(img_uint8, mask_edge, i, resolution)
		result_pred = extract_front_indicators(img_uint8, pred_uint8, i, resolution)
		
		if result_pred is None or result_mask is None:
#			print(raw_path, 'mean distance from front: NaN - unable to extract front')
			continue
		
		mask_test = np.zeros(resolution)
		pred_test = np.zeros(resolution)
		
		front_line_mask = result_mask[1]
		front_line_pred = result_pred[1]
		front_contour_mask = []
		front_contour_pred = []
		for j in range(len(front_line_mask[0])):
			front_contour_mask.append([front_line_mask[0][j], front_line_mask[1][j]])
		for j in range(len(front_line_pred[0])):
			front_contour_pred.append([front_line_pred[0][j], front_line_pred[1][j]])
		

				
		front_contour_mask = np.array([front_contour_mask], dtype=np.int32)
		cv2.fillPoly(mask_test, front_contour_mask, 255)
#		plt.figure(i * 2)
#		plt.clf()
#		plt.imshow(mask_test)
#		plt.show()
#		return
		front_contour_pred = np.array([front_contour_pred], dtype=np.int32)
		cv2.fillPoly(pred_test, front_contour_pred, 255)
#		plt.figure(i * 2 + 1)
#		plt.clf()
#		plt.imshow(pred_test)
#		plt.show()
		
		intersection = np.logical_xor(mask_test, pred_test)
		line_length = cv2.arcLength(front_contour_mask, False)
		error_area = np.sum(intersection)
		mean_error_per_unit = error_area / line_length
		
		x_scale = resolution_original[0] / resolution[0]
		y_scale = resolution_original[1] / resolution[1]
		norm_scale = np.sqrt(x_scale * x_scale + y_scale * y_scale)
		landsat_resolution = 30
		if band == 'B7':
			landsat_resolution = 60
		
		mean_error_per_meter = mean_error_per_unit * norm_scale * landsat_resolution
		mean_errors[domain].append(mean_error_per_meter)
#		print(raw_path, 'mean distance from front:', str(mean_error_per_meter) + 'm') 
#		raise Exception()
#		img_f64 = resize(img_uint16, (img_size, img_size), preserve_range=True)  #np.float64 [0.0, 65535.0]
#		mask_f64 = resize(mask_uint16, (img_size, img_size), order=0, preserve_range=True) #np.float64 [0.0, 65535.0]
#	
	for domain, error_array in mean_errors.items():
		print(domain, 'mean distance from front:', str(np.mean(error_array)) + 'm', 'median:', str(np.median(error_array)) + 'm')
		