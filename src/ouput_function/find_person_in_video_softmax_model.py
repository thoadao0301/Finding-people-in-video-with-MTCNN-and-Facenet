"""Using model in finding people in video."""
#   MIT License
#  Copyright (c) 2021. TranPhuongNam,DaoLeBaoThoa,NguyenDiemUyenPhuong
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import sys
import os
import ffmpeg
import numpy as np
import cv2
import pickle
import argparse
import tensorflow as tf
import warnings
warnings.filterwarnings("ignore")

from mtcnn import MTCNN
from moviepy.editor import *
from tqdm import tqdm
from datetime import datetime
from PIL import Image

def extract_faces(img_array, detector, image_size=160, margin=44):
    faces_list, bbox = [], []
    # convert channel
    img = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)

    results = detector.detect_faces(img)
    # extract the bounding box from the first face
    for face in results:
        confidence = face['confidence']
        if confidence < 0.8:
            continue
        face_bbox = face['box']
        x1, y1, width, height = face_bbox

        # bug fix
        x1, y1 = abs(x1), abs(y1)
        x2, y2 = x1 + width, y1 + height

        x1 = x1 - margin / 2 if x1 - margin / 2 > 0 else 0
        y1 = y1 - margin / 2 if y1 - margin / 2 > 0 else 0
        x2 = x2 + margin / 2 if x2 + margin / 2 < img.shape[1] else img.shape[1]
        y2 = y2 + margin / 2 if y2 + margin / 2 < img.shape[0] else img.shape[0]
        x1, x2, y1, y2 = int(x1), int(x2), int(y1), int(y2)

        # extract the face
        face = img[y1:y2, x1:x2]
        # resize pixels to the model size
        face = Image.fromarray(face)
        face = face.resize((image_size,image_size))
        faces_list.append(face)
        bbox.append(face_bbox)

    return faces_list, bbox

def draw_bbox(image,bbox,text):
  x,y,w,h = bbox
  cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
  cv2.putText(image, text,(x, y),
              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
  return image

def out_txt(output_loc,duration,text):
    out_file = open(output_loc + '/list_faces.txt','a')
    out_file.write(f'\nTime({duration}),{text}')
    out_file.close()



def out_video(images_video_dir,input_video, output_loc, fps=15):
    # Python code to convert video to audio

    # Insert Local Video File Path
    clip = VideoFileClip(input_video)
    # Insert Local Audio File Path
    out_audio=os.path.join(output_loc,'audio.wav')
    out_video = os.path.join(output_loc, "result_vid.mp4")
    export_video = os.path.join(output_loc, "result_vid_with_audio.mp4")
    clip.audio.write_audiofile(out_audio,codec='pcm_s16le')


    list_file = os.listdir(images_video_dir)
    filename = f'{images_video_dir}/{list_file[0]}'
    img = cv2.imread(filename)
    height, width, layers = img.shape
    size = (width, height)
    out = cv2.VideoWriter(out_video, cv2.VideoWriter_fourcc(*'DIVX'), 30, size)
    with tqdm(total=len(list_file) - 1, file=sys.stdout) as pbar:
      for i in range(1, len(list_file)):
          filename = f'{images_video_dir}/{i}.jpg'
          img = cv2.imread(filename)
          out.write(img)
          pbar.update(1)
    out.release()

    video_stream = ffmpeg.input(out_video)
    audio_stream = ffmpeg.input(out_audio)
    ffmpeg.output(video_stream, audio_stream, export_video).run()

    os.remove(out_video)
    os.remove(out_audio)


def detect_face(image, id, frame_number,frame_count, fps, model, output_loc ,detector, export_video, threshold=0.5):
    name_tag = ""
    time_start = []
    # Get model and class_names
    model, class_names = model
    # create the detector, using default weights
    faces_list, bboxs_list = extract_faces(image, detector, image_size=160)
    # loop through each face in detections
    if len(faces_list) == 0 and export_video:
        image_path = os.path.join(output_loc, 'images')
        cv2.imwrite(f'{image_path}/{frame_number}.jpg', image)
        return
    for i in range(len(faces_list)):

        # get embedded image
        # Get input and output tensors
        img = faces_list[i].convert('RGB')
        # resize image
        img = tf.cast(np.array(img), tf.float32) / 255
        # get embeddings for the faces in an image
        img = tf.expand_dims(img, axis=0)

        predictions = model.predict(img)

        # get coordinates (x,y) and weight, height (w, h) of the bounding box
        bbox = bboxs_list[i]

        # get predict from model
        class_index = np.argmax(predictions, axis=1)

        # get label name
        predict_name = class_names[class_index[0]]

        # get probability
        class_probability = predictions[0, class_index] * 100
        threshold *= 100

        # Accept with the probability > threshold

        duration = round(frame_number / fps, 2)
        time_cur = [int(duration / 3600), int((duration % 3600) / 60), (duration % 3600) % 60]

        if id != -1:
            if class_probability > threshold and class_index == id:
                text = f'{predict_name}:{class_probability}'
                dura = "{:0>2}:{:0>2}:{:0>2.0f}".format(time_cur[0], time_cur[1], time_cur[2])
                out_txt(output_loc, dura, text)
                image = draw_bbox(image, bbox, text)
        elif class_probability > threshold:
            text = f'{predict_name}:{class_probability}'
            image = draw_bbox(image, bbox, text)
            if name_tag == "":
                name_tag, time_start = predict_name, time_cur
            elif (name_tag != predict_name):
                dura = "{:0>2}:{:0>2}:{:0>2.0f}-{:0>2}:{:0>2}:{:0>2.0f}".format(time_start[0], time_start[1],
                                                                                time_start[2], time_cur[0], time_cur[1],
                                                                                time_cur[2])
                out_txt(output_loc, dura, name_tag)
                # reset
                name_tag, time_start = predict_name, time_cur

    if export_video:
        image_path = os.path.join(output_loc, 'images')
        cv2.imwrite(f'{image_path}/{frame_number}.jpg', image)
    if frame_number == frame_count and id == -1:
        dura = "{:0>2}:{:0>2}:{:0>2.0f}-{:0>2}:{:0>2}:{:0>2.0f}".format(time_start[0], time_start[1], time_start[2],
                                                                        time_cur[0], time_cur[1], time_cur[2])
        out_txt(output_loc, dura, name_tag)

def main(args):

    # Create folder
    now = datetime.now()
    dt_string = now.strftime("%d%m%Y%H%M%S")
    output_loc = os.path.join(args.output_loc, dt_string)
    os.mkdir(output_loc)

    with tf.device('/GPU:0'):

        # Load facenet model
        print('Loading feature extraction model')
        model = tf.keras.models.load_model(args.model_path)
        model.load_weights(args.model_weights_path)

        # Create mtcnn model
        detector = MTCNN()

        # Load class name
        with open(args.class_names, 'rb') as infile:
            class_names = pickle.load(infile)

        # Read video
        cap = cv2.VideoCapture(args.input_video)

        # Get fpt from video
        fps = cap.get(cv2.CAP_PROP_FPS)
        # Get frame information
        if args.frame_skip == 0:
            frame_skip = int(fps)
        else:
            frame_skip = args.frame_skip
        if args.export_video:
            frame_skip=1
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_number = 0
        print(frame_skip)
        # Not finding an exact face


        # Create folder images for export video
        if args.export_video:
            images_video_dir = os.path.join(output_loc, 'images')
            os.mkdir(images_video_dir)
        print('Processing video...')
        with tqdm(total=(frame_count//frame_skip), file=sys.stdout) as pbar:
            while cap.isOpened():
                # Extract the frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                if ret == True:
                    # Face Detection
                    detect_face(frame, args.id, frame_number,frame_count, fps,
                                (model, class_names), output_loc,
                                detector, args.export_video, args.threshold)
                    if args.export_video:
                        img_path = f'{images_video_dir}/{frame_number}.jpg'
                        cv2.imwrite(img_path, frame)
                    frame_number += frame_skip
                else:
                    break
                pbar.update(1)
        cap.release()
        print('Successful write .txt file')

        # Export video
        if args.export_video:
            print('Rendering video...')
            out_video(images_video_dir, args.input_video, output_loc, fps)
            print('Successful export .mp4 file: ')

def parse_arguments(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('model_path', type=str,
                        help='Path to the facenet model training with softmax')
    parser.add_argument('model_weights_path', type=str,
                        help='Path to the facenet model weights training with softmax')
    parser.add_argument('class_names', type=str,
                        help='Path to the class_names in training classifier model')
    parser.add_argument('input_video', type=str,
                        help='Video for extract face')
    parser.add_argument('output_loc', type=str,
                        help='Output location folder')
    parser.add_argument('--export_video', type=bool,
                        help='For export video with draw boundings box', default=False)
    parser.add_argument('--frame_skip', type=int,
                        help='For skip frame read, default is 0', default=0)
    parser.add_argument('--threshold', type=float,
                        help='Threshold for predict image', default=0.5)
    parser.add_argument('--id', type=int,
                        help='ID of specific person', default=-1)
    return parser.parse_args(argv)


if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))