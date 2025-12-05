import cv2
import numpy as np
import uuid
import random

ALL_VIDEO_EFFECTS = [
    "shake", "zoom", "glitch", "boomerang", "slowmo", "neon", "rotate",
    "kaleidoscope", "rainbow", "vibrance", "invert", "fire", "hologram", "vhs", "epic"
]

def apply_video_effect(input_path: str, effect_name: str) -> str:
    cap = cv2.VideoCapture(input_path)
    fourcc = cv2.VideoWriter_fourcc(*'VP90')
    out_path = f"/tmp/{uuid.uuid4()}.webm"
    out = cv2.VideoWriter(out_path, fourcc, 30, (512, 512))

    frame_count = 0
    max_frames = 180  # 6 секунд

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.resize(frame, (512, 512))
        t = frame_count / 30.0

        if effect_name == "shake":
            if random.random() < 0.7:
                dx = random.randint(-40, 40)
                dy = random.randint(-40, 40)
                M = np.float32([[1,0,dx],[0,1,dy]])
                frame = cv2.warpAffine(frame, M, (512,512))

        elif effect_name == "zoom":
            scale = 1 + 0.5 * np.sin(t * 10)
            M = cv2.getRotationMatrix2D((256,256), 0, scale)
            frame = cv2.warpAffine(frame, M, (512,512))

        elif effect_name == "glitch":
            if frame_count % 6 < 2:
                frame = cv2.addWeighted(frame, 0.8, cv2.applyColorMap(frame, cv2.COLORMAP_JET), 0.3, 0)

        elif effect_name == "boomerang":
            if int(t * 15) % 2 == 1: continue

        elif effect_name == "slowmo":
            if frame_count % 2 == 1: continue

        elif effect_name == "neon":
            frame = cv2.applyColorMap(frame, cv2.COLORMAP_TWILIGHT_SHIFTED)

        elif effect_name == "rotate":
            angle = t * 180
            M = cv2.getRotationMatrix2D((256,256), angle, 1)
            frame = cv2.warpAffine(frame, M, (512,512))

        elif effect_name == "kaleidoscope":
            h, w = frame.shape[:2]
            frame[:h//2, :w//2] = cv2.flip(frame[:h//2, :w//2], 1)
            frame[h//2:, :] = cv2.flip(frame[:h//2, :], 0)

        elif effect_name == "rainbow":
            hue = int(t * 180) % 180
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv[..., 0] = hue
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        elif effect_name == "vibrance":
            frame = cv2.convertScaleAbs(frame, alpha=2.0, beta=30)

        elif effect_name == "invert":
            if frame_count % 10 < 5: frame = cv2.bitwise_not(frame)

        elif effect_name == "fire":
            mask = cv2.inRange(frame, (0,0,100), (50,50,255))
            fire = cv2.applyColorMap(mask, cv2.COLORMAP_HOT)
            frame = cv2.addWeighted(frame, 0.8, fire, 0.4, 0)

        elif effect_name == "hologram":
            noise = np.random.normal(0, 30, frame.shape).astype(np.uint8)
            frame = cv2.add(frame, noise)
            frame = cv2.applyColorMap(frame, cv2.COLORMAP_PLASMA)

        elif effect_name == "vhs":
            if random.random() < 0.15:
                cv2.line(frame, (0, random.randint(0,512)), (512, random.randint(0,512)), (200,200,200), 3)
            frame = cv2.convertScaleAbs(frame, alpha=1.3, beta=-30)

        elif effect_name == "epic":
            scale = 1 + 0.4 * np.sin(t * 6)
            M = cv2.getRotationMatrix2D((256,256), 0, scale)
            frame = cv2.warpAffine(frame, M, (512,512))
            vignette = np.zeros((512,512), np.uint8)
            cv2.circle(vignette, (256,256), 280, 255, -1)
            frame = cv2.subtract(frame, vignette[..., None])

        if frame_count % 2 == 0:
            out.write(frame)
        frame_count += 1

    cap.release()
    out.release()
    return out_path
