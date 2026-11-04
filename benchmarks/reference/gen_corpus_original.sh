#!/bin/bash
# Synthetic media corpus for comparing ffprobe and MediaInfoLib. Usage: gen_corpus.sh <new-dir>
set -u
C=${1:?usage: gen_corpus.sh <new-dir>}; mkdir "$C" && cd "$C" || exit 1
F="ffmpeg -hide_banner -loglevel error -y"
V10="-f lavfi -i testsrc2=size=320x240:rate=25:duration=10"
V61="-f lavfi -i testsrc2=size=320x240:rate=25:duration=61.5"
A10="-f lavfi -i sine=frequency=440:sample_rate=48000:duration=10"
A61="-f lavfi -i sine=frequency=440:sample_rate=44100:duration=61.5"
T=(-metadata "artist=Spike Artist" -metadata "title=Spike Title" -metadata "album=Spike Album")
$F -f lavfi -i testsrc2=size=300x300:duration=1 -frames:v 1 cover.jpg
g() { local out=$1; shift; $F "$@" "$out" 2>>gen.err || echo "FAILED $out" >> gen.err; }
g 01-h264-aac.mp4        $V61 $A61 -c:v libx264 -preset ultrafast -c:a aac -b:a 128k "${T[@]}" -shortest
g 02-hevc-opus.mkv       $V10 $A10 -c:v libx265 -preset ultrafast -c:a libopus -b:a 96k "${T[@]}" -shortest
g 03-vp9-vorbis.webm     $V10 $A10 -c:v libvpx-vp9 -deadline realtime -cpu-used 8 -b:v 300k -c:a libvorbis "${T[@]}" -shortest
g 04-av1-flac.mkv        $V10 $A10 -c:v libsvtav1 -preset 12 -c:a flac "${T[@]}" -shortest
g 05-xvid-mp3.avi        $V61 $A61 -c:v libxvid -c:a libmp3lame -b:a 192k "${T[@]}" -shortest
g 06-mpeg4-mp3.avi       $V10 $A10 -c:v mpeg4 -c:a libmp3lame -b:a 128k "${T[@]}" -shortest
g 07-mpeg2-mp2.mpg       $V10 $A10 -c:v mpeg2video -c:a mp2 -f vob "${T[@]}" -shortest
g 08-mpeg1-mp2.mpg       $V10 $A10 -c:v mpeg1video -c:a mp2 "${T[@]}" -shortest
g 09-h264-ac3.ts         $V10 $A10 -c:v libx264 -preset ultrafast -c:a ac3 "${T[@]}" -shortest
g 10-h264-alac.mov       $V10 $A10 -c:v libx264 -preset ultrafast -c:a alac "${T[@]}" -shortest
g 11-wmv2-wmav2.wmv      $V10 $A10 -c:v wmv2 -c:a wmav2 "${T[@]}" -shortest
g 12-theora-vorbis.ogv   $V10 $A10 -c:v libtheora -c:a libvorbis "${T[@]}" -shortest
g 13-h264-aac.flv        $V10 $A10 -c:v libx264 -preset ultrafast -c:a aac "${T[@]}" -shortest
g 14-multi-audio-sub.mkv $V10 $A10 -f lavfi -i sine=frequency=880:duration=10 -map 0:v -map 1:a -map 2:a -c:v libx264 -preset ultrafast -c:a:0 aac -c:a:1 ac3 "${T[@]}" -shortest
g 15-prores-pcm.mov      -f lavfi -i testsrc2=size=320x240:rate=25:duration=3 -f lavfi -i sine=duration=3 -c:v prores_ks -profile:v 0 -c:a pcm_s16le "${T[@]}" -shortest
g 16-mjpeg-pcm.avi       $V10 $A10 -c:v mjpeg -c:a pcm_s16le "${T[@]}" -shortest
g 17-h263-aac.3gp        -f lavfi -i testsrc2=size=176x144:rate=15:duration=10 $A10 -c:v h263 -c:a aac -ar 16000 -ac 1 "${T[@]}" -shortest
g 18-cbr-cover.mp3       $A61 -i cover.jpg -map 0:a -map 1:v -c:a libmp3lame -b:a 192k -c:v copy -id3v2_version 3 -disposition:v attached_pic "${T[@]}"
g 19-vbr-xing.mp3        $A61 -c:a libmp3lame -q:a 2 "${T[@]}"
g 20-vbr-noxing.mp3      $A61 -c:a libmp3lame -q:a 2 -write_xing 0 "${T[@]}"
g 21-flac-cover.flac     $A61 -i cover.jpg -map 0:a -map 1:v -c:a flac -c:v copy -disposition:v attached_pic "${T[@]}"
g 22-vorbis.ogg          $A61 -c:a libvorbis "${T[@]}"
g 23-opus.opus           $A61 -c:a libopus -b:a 64k "${T[@]}"
g 24-aac-cover.m4a       $A61 -i cover.jpg -map 0:a -map 1:v -c:a aac -b:a 160k -c:v copy -disposition:v attached_pic "${T[@]}"
g 25-pcm16.wav           $A10 -c:a pcm_s16le "${T[@]}"
g 26-pcm16be.aiff        $A10 -c:a pcm_s16be "${T[@]}"
g 27-eac3.mka            $A10 -c:a eac3 "${T[@]}"
g 28-dts.mka             $A10 -c:a dca -strict -2 "${T[@]}"
g 29-raw.h264            $V10 -c:v libx264 -preset ultrafast -f h264
g 30-raw-adts.aac        $A61 -c:a aac -b:a 128k -f adts
rm -f cover.jpg
ls | wc -l
