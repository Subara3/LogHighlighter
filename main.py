import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import os
import time
import json
import urllib
import logging
import requests
from pydub import AudioSegment
from threading import Thread
import re

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

endpoint = 'https://acp-api-async.amivoice.com/v1/recognitions'
app_key = 'YOUR-API-KEY'

models = {
    "会話_汎用": "-a-general",
    "会話_医療": "-a-medgeneral",
    "会話_製薬": "-a-bizmrreport",
    "会話_金融": "-a-bizfinance",
    "会話_保険": "-a-bizinsurance",
    "音声入力_汎用": "-a-general-input",
    "音声入力_医療": "-a-medgeneral-input",
    "音声入力_製薬": "-a-bizmrreport-input",
    "音声入力_金融": "-a-bizfinance-input",
    "音声入力_保険": "-a-bizinsurance-input",
    "音声入力_電子カルテ": "-a-medkarte-input",
    "英語_汎用": "-a-general-en",
    "中国語_汎用": "-a-general-zh",
    "韓国語_汎用": "-a-general-ko"
}

sentiment_parameters = {
    "energy": (0, 100, "エネルギー"),
    "stress": (0, 100, "ストレス"),
    "emo_cog": (1, 500, "感情バランス論理"),
    "concentration": (0, 100, "濃縮"),
    "anticipation": (0, 100, "期待"),
    "excitement": (0, 30, "興奮した"),
    "hesitation": (0, 30, "躊躇"),
    "uncertainty": (0, 30, "不確実"),
    "intensive_thinking": (0, 100, "考える"),
    "imagination_activity": (0, 30, "想像"),
    "embarrassment": (0, 30, "困惑した"),
    "passionate": (0, 30, "情熱"),
    "brain_power": (0, 100, "脳活動"),
    "confidence": (0, 30, "自信"),
    "aggression": (0, 30, "攻撃性憤り"),
    "atmosphere": (-100, 100, "雰囲気会話傾向"),
    "upset": (0, 30, "動揺"),
    "content": (0, 30, "喜び"),
    "dissatisfaction": (0, 30, "不満"),
    "extreme_emotion": (0, 30, "極端な起伏"),
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Speech Recognition with Diarization and Sentiment Analysis")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, padx=10, pady=10)

        self.tab1 = tk.Frame(self.notebook)
        self.tab2 = tk.Frame(self.notebook)
        self.tab3 = tk.Frame(self.notebook)

        self.notebook.add(self.tab1, text="音声変換")
        self.notebook.add(self.tab2, text="中身の処理")
        self.notebook.add(self.tab3, text="感情パラメーター設定")

        # Tab 1: 音声変換
        self.file_label = tk.Label(self.tab1, text="File Name:")
        self.file_label.grid(row=0, column=0, padx=10, pady=10)
        self.file_entry = tk.Entry(self.tab1, width=50)
        self.file_entry.grid(row=0, column=1, padx=10, pady=10)
        self.file_button = tk.Button(self.tab1, text="Browse", command=self.browse_file)
        self.file_button.grid(row=0, column=2, padx=10, pady=10)

        self.speaker_label = tk.Label(self.tab1, text="Number of Speakers:")
        self.speaker_label.grid(row=1, column=0, padx=10, pady=10)
        self.speaker_spinbox = tk.Spinbox(self.tab1, from_=1, to=20)
        self.speaker_spinbox.grid(row=1, column=1, padx=10, pady=10)

        self.model_label = tk.Label(self.tab1, text="Model:")
        self.model_label.grid(row=3, column=0, padx=10, pady=10)
        self.model_var = tk.StringVar(self.tab1)
        self.model_var.set(list(models.keys())[0])
        self.model_menu = ttk.Combobox(self.tab1, textvariable=self.model_var, values=list(models.keys()))
        self.model_menu.grid(row=3, column=1, padx=10, pady=10)

        self.progress_frame = tk.Frame(self.tab1)
        self.progress_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10)
        self.progress_bars = []
        self.progress_labels = []

        self.start_button = tk.Button(self.tab1, text="Start", command=self.start_recognition)
        self.start_button.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

        self.results_label = tk.Label(self.tab1, text="Results:")
        self.results_label.grid(row=6, column=0, padx=10, pady=10)
        self.results_text = tk.Text(self.tab1, width=60, height=20)
        self.results_text.grid(row=7, column=0, columnspan=3, padx=10, pady=10)

        self.time_label = tk.Label(self.tab1, text="Time Taken:")
        self.time_label.grid(row=8, column=0, padx=10, pady=10)
        self.time_text = tk.Label(self.tab1, text="")
        self.time_text.grid(row=8, column=1, padx=10, pady=10)

        # Tab 2: 中身の処理
        self.process_button = tk.Button(self.tab2, text="Process Saved Results", command=self.process_saved_results)
        self.process_button.grid(row=0, column=0, padx=10, pady=10)
        self.processed_results_label = tk.Label(self.tab2, text="Processed Results:")
        self.processed_results_label.grid(row=1, column=0, padx=10, pady=10)
        self.processed_results_text = tk.Text(self.tab2, width=60, height=20)
        self.processed_results_text.grid(row=2, column=0, columnspan=3, padx=10, pady=10)

        # Tab 3: 感情パラメーター設定
        self.canvas = tk.Canvas(self.tab3)
        self.scrollbar = ttk.Scrollbar(self.tab3, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.tab3.grid_rowconfigure(0, weight=1)
        self.tab3.grid_columnconfigure(0, weight=1)

        self.sentiment_vars = {}
        self.markup_vars = {}

        for i, (param, (min_val, max_val, label)) in enumerate(sentiment_parameters.items()):
            self.sentiment_vars[param] = tk.IntVar(value=min_val)
            self.markup_vars[param] = tk.BooleanVar(value=False)

            tk.Label(self.scrollable_frame, text=label).grid(row=i, column=0, padx=5, pady=5)
            tk.Scale(self.scrollable_frame, from_=min_val, to=max_val, orient="horizontal",
                     variable=self.sentiment_vars[param]).grid(row=i, column=1, padx=5, pady=5)
            tk.Checkbutton(self.scrollable_frame, text="Markup", variable=self.markup_vars[param]).grid(row=i, column=2, padx=5, pady=5)

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav")])
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)

    def start_recognition(self):
        filename = self.file_entry.get()
        num_speakers = int(self.speaker_spinbox.get())
        self.selected_model = models[self.model_var.get()]
        self.start_time = time.time()  # 開始時間を記録

        for widget in self.progress_frame.winfo_children():
            widget.destroy()
        self.progress_bars.clear()
        self.progress_labels.clear()

        audio = AudioSegment.from_wav(filename)
        chunk_length_ms = 3 * 60 * 60 * 1000  # 3 hours
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

        self.num_chunks = len(chunks)
        self.completed_chunks = 0

        for i in range(self.num_chunks):
            label = tk.Label(self.progress_frame, text=f"Chunk {i + 1}/{self.num_chunks}")
            label.grid(row=i, column=0, padx=10, pady=5)
            progress = ttk.Progressbar(self.progress_frame, orient="horizontal", length=300, mode="determinate")
            progress.grid(row=i, column=1, padx=10, pady=5)
            self.progress_labels.append(label)
            self.progress_bars.append(progress)

        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Starting recognition...\n")

        for i, chunk in enumerate(chunks):
            chunk_filename = f"chunk_{i}.wav"
            chunk.export(chunk_filename, format="wav")
            Thread(target=self.process_chunk, args=(chunk_filename, num_speakers, i)).start()

    def process_chunk(self, chunk_filename, num_speakers, index):
        domain = {
            'grammarFileNames': self.selected_model,
            'loggingOptOut': 'True',
            'contentId': chunk_filename,
            'speakerDiarization': 'True',
            'diarizationMinSpeaker': str(num_speakers),
            'diarizationMaxSpeaker': str(num_speakers),
            'sentimentAnalysis': 'True',
        }
        params = {
            'u': app_key,
            'd': ' '.join([f'{key}={urllib.parse.quote(value)}' for key, value in domain.items()]),
        }
        logger.info(params)

        try:
            with open(chunk_filename, 'rb') as f:
                request_response = requests.post(
                    url=endpoint,
                    data={key: value for key, value in params.items()},
                    files={'a': (chunk_filename, f.read(), 'application/octet-stream')}
                )

            if request_response.status_code != 200:
                logger.error(f'Failed to request - {request_response.content}')
                return

            request = request_response.json()

            if 'sessionid' not in request:
                logger.error(f'Failed to create job - {request["message"]} ({request["code"]})')
                return

            logger.info(request)

            while True:
                result_response = requests.get(
                    url=f'{endpoint}/{request["sessionid"]}',
                    headers={'Authorization': f'Bearer {app_key}'}
                )
                if result_response.status_code == 200:
                    result = result_response.json()
                    if 'status' in result and (result['status'] == 'completed' or result['status'] == 'error'):
                        self.results_text.insert(tk.END, f"Chunk {index + 1} completed.\n")
                        self.update_progress(index, 100)
                        self.save_chunk_result(index, result)
                        self.completed_chunks += 1
                        if self.completed_chunks == self.num_chunks:
                            self.results_text.insert(tk.END, "All chunks processed. Combining results...\n")
                            self.combine_results()
                            self.update_time_label()  # Move the update time label here
                        break
                    else:
                        logger.info(result)
                        self.update_progress(index, 10)
                        time.sleep(10)
                else:
                    logger.error(f'Failed. Response is {result_response.content}')
                    break
        except Exception as e:
            logger.error(f'An error occurred: {e}')
        finally:
            os.remove(chunk_filename)

    def update_progress(self, index, increment):
        self.progress_bars[index]["value"] += increment
        self.update_idletasks()

    def save_chunk_result(self, index, result):
        with open(f"chunk_{index}_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

    def update_time_label(self):
        elapsed_time = time.time() - self.start_time
        self.time_text.config(text=f"{elapsed_time:.2f} seconds")

    def combine_results(self):
        combined_result = {"speakers": {}, "sentiments": {}}
        for i in range(self.num_chunks):
            chunk_result_filename = f"chunk_{i}_result.json"
            with open(chunk_result_filename, 'r', encoding='utf-8') as f:
                chunk_result = json.load(f)
                if "segments" in chunk_result:
                    for segment in chunk_result["segments"]:
                        if "results" in segment:
                            for result in segment["results"]:
                                for token in result["tokens"]:
                                    speaker = token.get("label", "Unknown Speaker")
                                    text = token.get("written", "")
                                    if speaker not in combined_result["speakers"]:
                                        combined_result["speakers"][speaker] = []
                                    combined_result["speakers"][speaker].append({
                                        "text": text,
                                        "starttime": token.get("starttime"),
                                        "endtime": token.get("endtime")
                                    })
                if "sentiment_analysis" in chunk_result:
                    for sentiment_segment in chunk_result["sentiment_analysis"]["segments"]:
                        starttime = sentiment_segment.get("starttime")
                        endtime = sentiment_segment.get("endtime")
                        sentiments = sentiment_segment  # Store the whole sentiment segment
                        del sentiments["starttime"]
                        del sentiments["endtime"]
                        if speaker not in combined_result["sentiments"]:
                            combined_result["sentiments"][speaker] = []
                        combined_result["sentiments"][speaker].append({
                            "starttime": starttime,
                            "endtime": endtime,
                            "sentiments": sentiments
                        })

            os.remove(chunk_result_filename)

        with open("combined_result.json", 'w', encoding='utf-8') as f:
            json.dump(combined_result, f, ensure_ascii=False, indent=4)
        
        self.process_saved_results()

    def process_saved_results(self):
        with open("combined_result.json", 'r', encoding='utf-8') as f:
            combined_result = json.load(f)
        
        final_text = ""
        for speaker, texts in combined_result["speakers"].items():
            combined_text = ''.join([text["text"] for text in texts])
            combined_text = re.sub(r' (?=[^\x00-\x7F])', '', combined_text)
            
            # Markup the excitement parts
            if speaker in combined_result["sentiments"]:
                for sentiment in combined_result["sentiments"][speaker]:
                    for param, threshold in self.sentiment_vars.items():
                        if self.markup_vars[param].get():
                            if param in sentiment["sentiments"] and sentiment["sentiments"][param] > threshold.get():
                                combined_text = self.markup_excitement(combined_text, texts, sentiment["starttime"], sentiment["endtime"], param)
            
            final_text += f"{speaker}: {combined_text}\n"
        
        self.processed_results_text.delete(1.0, tk.END)
        self.processed_results_text.insert(tk.END, final_text)

    def markup_excitement(self, combined_text, texts, start, end, param):
        for text in texts:
            if text["starttime"] >= start and text["endtime"] <= end:
                combined_text = combined_text.replace(text["text"], f"【{param.upper()}: {text['text']}】")
        return combined_text

if __name__ == "__main__":
    app = App()
    app.mainloop()
