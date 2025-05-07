import cv2
from ultralytics import YOLO

def main():
    # 1) Carrega modelo YOLOv8 nano otimizado para GPU
    model = YOLO('yolov8n.pt').to('cuda')

    # 2) URL da sua stream RTMP
    stream_url = 'rtmp://192.168.0.202:1935/live/stream'
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print(f"Erro ao abrir stream: {stream_url}")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 3) Inferência (detecta todas as classes; filtramos só 'person')
        results = model(frame, verbose=False)[0]
        # 4) Desenha somente caixas de "person"
        for box, cls in zip(results.boxes.xyxy, results.boxes.cls):
            if model.names[int(cls)] == 'person':
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
                cv2.putText(frame, 'person', (x1, y1-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        # 5) Exibe no monitor
        cv2.imshow('YOLOv8 Person Detection', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()