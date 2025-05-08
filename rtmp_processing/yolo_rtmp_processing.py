import cv2
import time
import argparse
import numpy as np
from ultralytics import YOLO

def parse_args():
    parser = argparse.ArgumentParser(description="YOLOv8 RTMP Multi-Classe")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                        help="Caminho para o peso do modelo YOLOv8")
    parser.add_argument("--source", type=str, default="rtmp://192.168.0.202:1935/live/stream",
                        help="URL RTMP ou caminho de vídeo")
    parser.add_argument("--classes", nargs="+", default=["person", "car"],
                        help="Lista de nomes de classe para detectar")
    parser.add_argument("--conf", type=float, default=0.3,
                        help="Limiar mínimo de confiança [0.0–1.0]")
    parser.add_argument("--cpu", action="store_true",
                        help="Forçar execução na CPU (padrão: GPU, se disponível)")
    parser.add_argument("--show-fps", action="store_true",
                        help="Exibir FPS na janela de saída")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Tamanho de redimensionamento")
    parser.add_argument("--half", action="store_true",
                        help="Usar FP16 na GPU")

    return parser.parse_args()

def main():
    args = parse_args()

    # 1) Carrega modelo
    device = "cpu" if args.cpu else "cuda"
    model = YOLO(args.model).to(device)

    # 2) Mapeia nomes para IDs de classe
    names = model.names  # ex: {0:'person', 1:'bicycle', 2:'car', ...}
    target_ids = [cid for cid, nm in names.items() if nm in args.classes]
    if not target_ids:
        print(f"Nenhuma das classes {args.classes} está disponível no modelo.")
        return

    # 3) Gera cores únicas para cada classe alvo
    np.random.seed(42)
    colors = {cid: tuple(np.random.randint(0, 255, 3).tolist()) for cid in target_ids}

    # 4) Abre stream RTMP
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        print(f"Erro ao abrir stream: {args.source}")
        return

    prev_time = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 5) Inferência (já filtra por classes e confiança)
        results = model(frame,
                        conf=args.conf,
                        classes=target_ids,
                        verbose=False)[0]

        # 6) Desenha caixas com label e confidence
        for box, cls_id, conf in zip(results.boxes.xyxy,
                                      results.boxes.cls,
                                      results.boxes.conf):
            x1, y1, x2, y2 = map(int, box)
            cls_id = int(cls_id)
            label = f"{names[cls_id]} {conf:.2f}"
            color = colors.get(cls_id, (0, 255, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # 7) Opcional: exibe FPS
        if args.show_fps:
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

        # 8) Exibe resultado
        cv2.imshow("YOLOv8 Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
