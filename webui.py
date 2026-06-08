"""mkexam Web 服务"""
import json, os, sys, http.server, urllib.parse, mimetypes, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mkexam.bank import BankManager, Question
from mkexam.bank.importer import export_to_csv, import_from_csv
from mkexam.exam import ExamSelector, PaperGenerator
from mkexam.exam.preset import list_presets, load_preset, save_preset, init_defaults
from mkexam.omml import fmt_plain
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
bank = BankManager()
init_defaults()
generator = PaperGenerator(OUTPUT_DIR)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888


class APIHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/subjects":
            self._json(bank.list_subjects())
        elif path == "/api/subject":
            name = query.get("name", [""])[0]
            sub = bank.get(name)
            if not sub:
                self._json({"error": "not found"}, 404)
                return
            # 为每题添加公式渲染文本和图片
            questions = []
            for q in sub.questions:
                q = dict(q)
                text = q.get("q", q.get("text", ""))
                q["q_plain"] = fmt_plain(text)
                # 图片（优先使用已存储的 image 字段）
                stored_img = q.get("image", "")
                if stored_img:
                    # data/img/image-xxx.png → /api/fig/image-xxx.png
                    fname = stored_img.replace("img/", "")
                    q["image_url"] = f"/api/fig/{urllib.parse.quote(fname)}"
                else:
                    img = _find_question_image(text, q.get("type", ""))
                    if img:
                        q["image_url"] = img
                # 选项也渲染
                opts = q.get("opts", q.get("options", []))
                q["opts_plain"] = [fmt_plain(o) for o in opts]
                questions.append(q)
            self._json({"name": name, "questions": questions, "counts": sub.count_by_type()})
        elif path == "/api/presets":
            presets = {}
            for name in list_presets():
                presets[name] = load_preset(name)
            self._json(presets)
        elif path.startswith("/static/"):
            self._serve_static()
        elif path.startswith("/api/fig/"):
            # 提供图片文件
            fname = urllib.parse.unquote(path.replace("/api/fig/", ""))
            for base_dir in [
                os.path.join(os.path.dirname(DATA_DIR), "uploads"),
                os.path.join(DATA_DIR, "img"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "electest", "电工电子技术", "figures"),
            ]:
                fp = os.path.join(base_dir, fname)
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    ctype = "image/png" if fname.endswith(".png") else "image/jpeg"
                    self.send_header("Content-Type", ctype)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                    return
            self._json({"error": "not found"}, 404)
        elif path.startswith("/api/image/"):
            # 在 figures 和 images 目录中查找
            for d in [os.path.join(os.path.dirname(DATA_DIR), "..", "electest", "电工电子技术", "figures"),
                      os.path.join(os.path.dirname(DATA_DIR), "..", "electest", "传感器单片机物联网", "images")]:
                fp = os.path.join(d, fname)
                if os.path.exists(fp):
                    with open(fp, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    ctype = "image/png" if fname.endswith(".png") else "image/jpeg"
                    self.send_header("Content-Type", ctype)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                    return
            self._json({"error": "not found"}, 404)
        elif path.startswith("/api/preview-docx/"):
            # 将生成的 docx 转 HTML 返回预览（禁止缓存）
            fname = urllib.parse.unquote(path.replace("/api/preview-docx/", ""))
            fp = os.path.join(OUTPUT_DIR, fname)
            if os.path.isfile(fp) and fname.endswith(".docx"):
                try:
                    import mammoth
                    with open(fp, "rb") as f:
                        result = mammoth.convert_to_html(f)
                    html = result.value
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                    self.send_header("Pragma", "no-cache")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                except Exception as e:
                    self._json({"error": str(e)}, 500)
            else:
                self._json({"error": "not found"}, 404)
        elif path == "/":
            self._serve_static_file("index.html")
        elif path.startswith("/api/output/"):
            # 提供生成的试卷下载
            fname = urllib.parse.unquote(path.replace("/api/output/", ""))
            fp = os.path.join(OUTPUT_DIR, fname)
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    content = f.read()
                self.send_response(200)
                ctype, _ = mimetypes.guess_type(fname)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                # 用百分号编码的 ASCII 文件名避免 header 编码问题
                ascii_name = urllib.parse.quote(fname)
                self.send_header("Content-Disposition", f'attachment; filename="{ascii_name}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            else:
                self._json({"error": "not found"}, 404)
        elif path == "/api/output":
            self._json(os.listdir(OUTPUT_DIR) if os.path.exists(OUTPUT_DIR) else [])
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        data = json.loads(body) if body else {}
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/preview":
            sub_name = data.get("subject")
            sections = data.get("sections", [])
            secs = [(s["title"], s["key"], s["count"], s["score"]) for s in sections]
            selector = ExamSelector(bank)
            selected = selector.auto_select(sub_name, secs)
            result = {}
            for key, qs in selected.items():
                tn = {"choice":"选择题","tf":"判断题","fill":"填空题",
                      "calc":"计算题","short":"简答题","analysis":"分析题"}.get(key, key)
                items = []
                for q in qs:
                    text = q.get("q", q.get("text", ""))
                    opts = q.get("opts", q.get("options", []))
                    # 优先用存储的 image 字段，回退到文本猜图
                    stored_img = q.get("image", "")
                    if stored_img:
                        fname = stored_img.replace("img/", "")
                        img_url = f"/api/fig/{urllib.parse.quote(fname)}"
                    else:
                        img_url = _find_question_image(text, key)
                    items.append({
                        "text": fmt_plain(text),
                        "opts": [fmt_plain(o) for o in opts[:4]],
                        "image": img_url,
                    })
                sp = 0
                for _, _k, _c, _s in secs:
                    if _k == key:
                        sp = _s
                result[key] = {"title": tn, "questions": items, "count": len(qs), "score": sp, "total": len(qs)*sp}
            self._json(result)
        elif path == "/api/validate":
            if self.command == "POST":
                sub_name = data.get("subject", "")
                secs = data.get("sections", [])
            else:
                sub_name = query.get("name", [""])[0]
                secs_str = query.get("sections", [""])[0]
                try:
                    secs = json.loads(secs_str) if secs_str else []
                except:
                    secs = []
            sub = bank.get(sub_name)
            if not sub:
                self._json({"error": "not found"}, 404)
                return
            result = {}
            all_ok = True
            for sec in secs:
                key = sec.get("key", "")
                count = sec.get("count", 0)
                qs = [q for q in sub.questions if q.get("type") == key]
                avail = len(qs)
                if avail < count:
                    result[key] = {"avail": avail, "need": count, "ok": False}
                    all_ok = False
                else:
                    result[key] = {"avail": avail, "need": count, "ok": True}
            result["all_ok"] = all_ok
            self._json(result)
        elif path == "/api/subject/types":
            name = query.get("name", [""])[0]
            sub = bank.get(name)
            if not sub:
                self._json({"error": "not found"}, 404)
                return
            type_list = list(sub.count_by_type().keys())
            self._json(type_list)
        elif path == "/api/generate":
            sub_name = data.get("subject")
            sections = data.get("sections", [])
            n = data.get("count", 1)
            label = data.get("label", "")
            header = data.get("header", {})
            # 清理旧的 preview 文件
            for old_f in os.listdir(OUTPUT_DIR):
                if "preview" in old_f and old_f.endswith(".docx"):
                    try: os.remove(os.path.join(OUTPUT_DIR, old_f))
                    except: pass
            secs = [(s["title"], s["key"], s["count"], s["score"]) for s in sections]
            selector = ExamSelector(bank)
            # 保存header供生成器使用
            generator.header_info = header
            if n == 1:
                selected = selector.auto_select(sub_name, secs)
                generator.generate(sub_name, selected, secs, label=label)
            else:
                selected_list = selector.batch_select(sub_name, secs, n)
                labels = [chr(65 + i) for i in range(n)]
                generator.batch_generate(sub_name, selected_list, secs, labels)
            self._json({"ok": True, "output": os.listdir(OUTPUT_DIR)})
        elif path == "/api/question/add":
            sub_name = data.get("subject")
            q = data.get("question", {})
            sub = bank.get(sub_name)
            if not sub or not q:
                self._json({"error": "invalid"}, 400)
                return
            new_q = Question(
                type=q.get("type", "choice"),
                q=q.get("q", ""),
                opts=q.get("opts", []),
                ans=q.get("ans", ""),
                ch=q.get("ch", ""),
                difficulty=int(q.get("difficulty", 1)),
            )
            sub.add(new_q)
            bank.save(sub_name)
            self._json({"ok": True, "id": new_q.id})
        elif path == "/api/question/batch":
            sub_name = data.get("subject")
            questions = data.get("questions", [])
            sub = bank.get(sub_name)
            if not sub:
                self._json({"error": "invalid"}, 400)
                return
            count = 0
            for q in questions:
                new_q = Question(
                    type=q.get("type", "choice"),
                    q=q.get("q", ""),
                    opts=q.get("opts", []),
                    ans=q.get("ans", ""),
                    ch=q.get("ch", ""),
                    difficulty=int(q.get("difficulty", 1)),
                )
                sub.add(new_q)
                count += 1
            bank.save(sub_name)
            self._json({"ok": True, "count": count})
        elif path == "/api/question/delete":
            sub_name = data.get("subject")
            qid = data.get("id")
            bank.delete_question(sub_name, qid)
            self._json({"ok": True})
        elif path == "/api/upload/image":
            # 接收上传的图片（支持 multipart 和 base64 JSON）
            content_type = self.headers.get("Content-Type", "")
            sub_name = data.get("subject", "") if data else ""
            if "multipart" in content_type:
                import io
                boundary = content_type.split("boundary=")[1].strip()
                body_bytes = self.rfile.read(content_len)
                # 简单解析：找图片数据
                parts = body_bytes.split(b"\r\n")
                img_data = b""
                fname = f"{int(time.time())}.png"
                in_data = False
                for line in parts:
                    if b"filename=" in line:
                        fn_match = re.search(r'filename="(.+?)"', line.decode("utf-8", errors="replace"))
                        if fn_match:
                            fname = f"{int(time.time())}_{fn_match.group(1)}"
                    if b"Content-Type: image/" in line:
                        in_data = True
                        continue
                    if in_data:
                        if line == b"\r" or line == b"":
                            continue
                        if boundary in line or b"------" in line:
                            break
                        img_data += line + b"\n"
                img_data = img_data.strip()
            elif data and data.get("base64"):
                import base64
                img_data = base64.b64decode(data["base64"].split(",")[-1])
                fname = f"{int(time.time())}.png"
            else:
                self._json({"error": "no image data"}, 400)
                return

            img_dir = os.path.join(os.path.dirname(DATA_DIR), "uploads")
            os.makedirs(img_dir, exist_ok=True)
            fpath = os.path.join(img_dir, fname)
            with open(fpath, "wb") as f:
                f.write(img_data)
            from urllib.parse import quote
            self._json({"ok": True, "url": f"/api/fig/{quote(fname)}"})
        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_static(self):
        # 用已解析的 path（不含 query string）
        path = urllib.parse.urlparse(self.path).path.lstrip("/")
        rel = os.path.relpath(path, "static")
        full = os.path.join(STATIC_DIR, rel)
        if not os.path.exists(full):
            self._json({"error": "not found"}, 404)
            return
        with open(full, "rb") as f:
            content = f.read()
        self.send_response(200)
        ctype, _ = mimetypes.guess_type(full)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def _serve_static_file(self, name):
        path = os.path.join(STATIC_DIR, name.split("?")[0])
        if not os.path.exists(path):
            self._json({"error": "not found"}, 404)
            return
        with open(path, "rb") as f:
            content = f.read()
        self.send_response(200)
        ctype, _ = mimetypes.guess_type(path)
        self.send_header("Content-Type", ctype or "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass


def _find_question_image(text, qtype=""):
    """从题目文本中查找配图，返回可访问的 URL 或 None"""
    import re, os
    # 电工电子技术图片
    m = re.search(r'图\s*(\d+)', text)
    if m:
        fig_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "electest", "电工电子技术", "figures")
        fname = f"图{m.group(1)}.png"
        if os.path.exists(os.path.join(fig_dir, fname)):
            from urllib.parse import quote
            return f"/api/fig/{quote(fname)}"
    # 关键词 → 图片文件名
    IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "electest", "传感器单片机物联网", "images")
    kw_map = {
        # 单片机
        "最小系统": "m401_min_sys", "数码管": "m402_led", "LED": "m402_led",
        "矩阵键盘": "m403_keypad", "晶振": "m406_crystal",
        "光耦": "m413_optocoupler", "继电器": "m414_relay_driver",
        "电源电路": "m415_power",
        # 传感器
        "应变": "s401_strain_gauge", "热电偶": "s402_thermocouple",
        "电容式": "s403_capacitive", "恒流源": "s404_const_current",
        "霍尔": "s405_hall", "仪表放大器": "s408_inst_amp",
        "低通滤波": "s411_lpf", "交流电桥": "s414_ac_bridge",
        "信号链": "s415_signal_chain",
        # IoT
        "三层架构": "iot401_3layer", "MQTT": "iot402_mqtt",
        "RS485": "iot403_rs485", "智能家居": "iot404_smarthome",
        "网关": "iot405_gateway", "电流环": "iot411_current_loop",
        "电源管理": "iot414_power_mgmt",
    }
    for kw, fn in kw_map.items():
        if kw in text:
            for ext in [".png", ".jpg"]:
                fp = os.path.join(IMG_DIR, fn + ext)
                if os.path.exists(fp):
                    return f"/api/fig/{fn}{ext}"
    return None


if __name__ == "__main__":
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    server = http.server.HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"🌐 http://localhost:{PORT}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
