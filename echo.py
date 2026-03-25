import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import struct
import hashlib
import sounddevice as sd
from collections import deque

# =================================================================
# 【11D 动力学实验室 V13.0 - 弦外之音：全视口标准对位版】
# 1. 坐标轴全回归：确保右侧散点图与熵值图具备完整的定量观测能力。
# 2. 视听一致性：左侧演示与波形垂直对位，右侧分析矩阵垂直对齐。
# 3. 弦外之音引擎：保留 Aletheia 实时音频合成与十六进制数字流。
# =================================================================

class ProInteractiveLab:
    def __init__(self):
        self.dt = 0.0075
        self.r0 = 1.6
        self.breath_amp = 0.45
        self.omega = 1.55
        self.paused = True  
        self.effective_t = 0  
        
        self.pos_a = np.array([1.0, 0.0, 0.0]); self.pos_b = np.array([1.001, 0.0, 0.0])
        self.vel_a = np.array([0.0, 1.85, 0.35]); self.vel_b = np.array([0.0, 1.85, 0.35])
        
        self.path_a, self.path_b = [], []
        self.vibration_sense = 1.35
        self.current_R = self.r0
        self.gravity_const = -4.2 
        
        self.last_echo_hex = "0" * 64
        self.echo_perturbation = 0.0
        self.cloud_buffer = deque(maxlen=600) 
        self.entropy_history = deque(maxlen=100) 
        self.wave_buffer = deque(maxlen=300) 

        self.sample_rate = 44100
        self.audio_phase = 0.0
        self.current_freq_a = 220.0; self.current_freq_b = 220.0

    def listen_echo(self):
        raw_stream = b""
        for vec in [self.pos_a, self.pos_b, self.vel_a, self.vel_b]:
            for comp in vec: raw_stream += struct.pack('d', comp)
        full_echo = hashlib.sha256(raw_stream).hexdigest()
        self.last_echo_hex = full_echo
        
        ux = int(full_echo[:8], 16) / 0xFFFFFFFF
        uy = int(full_echo[8:16], 16) / 0xFFFFFFFF
        self.cloud_buffer.append((ux, uy))
        
        self.current_freq_a = 200 + np.linalg.norm(self.vel_a) * 165
        self.current_freq_b = 200 + np.linalg.norm(self.vel_b) * 165
        
        echo_val = int(full_echo[-8:], 16) / 0xFFFFFFFF
        self.echo_perturbation = (echo_val - 0.5) * 0.032
        return full_echo

    def update(self):
        if not self.paused:
            self.effective_t += 1; self.listen_echo()
            for p, v, path in zip([self.pos_a, self.pos_b], [self.vel_a, self.vel_b], [self.path_a, self.path_b]):
                r_mag = np.linalg.norm(p) + 1e-9
                g_eff = self.gravity_const + self.echo_perturbation
                f_macro = g_eff * p / (r_mag**2.9)
                f_cy = self.vibration_sense * (1.0 + 0.65 * np.sin(self.omega * self.effective_t * 0.1)) * np.array([
                    np.sin(7 * p[0]), np.cos(7 * p[1]), np.sin(7 * p[2] + np.cos(p[0]))
                ])
                f = f_macro + f_cy
                v += f * self.dt; p += v * self.dt
                path.append(p.copy())
            self.current_R = self.r0 + self.breath_amp * np.sin(self.omega * self.effective_t * 0.1)

# --- 音频引擎 ---
def audio_callback(outdata, frames, time, status):
    if universe.paused: outdata.fill(0); return
    jitter = (int(universe.last_echo_hex[:2], 16) / 255.0) * 12.0
    t = (universe.audio_phase + np.arange(frames)) / universe.sample_rate
    l_wave = 0.12 * np.sin(2 * np.pi * (universe.current_freq_a + jitter) * t)
    r_wave = 0.12 * np.sin(2 * np.pi * (universe.current_freq_b - jitter) * t)
    outdata[:, 0] = l_wave; outdata[:, 1] = r_wave
    universe.audio_phase += frames
    for sample in l_wave[::16]: universe.wave_buffer.append(sample)

universe = ProInteractiveLab()
fig = plt.figure(facecolor='black', figsize=(16, 10))
plt.rcParams['toolbar'] = 'None'

# === 左侧对位视口 ===
ax_main = fig.add_axes([0.05, 0.45, 0.55, 0.5], projection='3d')
ax_main.set_facecolor('black'); ax_main.set_axis_off()

ax_wave = fig.add_axes([0.08, 0.18, 0.48, 0.18])
ax_wave.set_facecolor('#050505')
ax_wave.set_title("ECHO WAVEFORM (Oscilloscope)", color='yellow', fontsize=8, loc='left')
for s in ['bottom', 'top', 'right', 'left']: ax_wave.spines[s].set_color('#333')
ax_wave.tick_params(colors='gray', labelsize=7)
wave_line, = ax_wave.plot([], [], color='yellow', lw=1)
ax_wave.set_xlim(0, 300); ax_wave.set_ylim(-0.3, 0.3)
ax_wave.grid(True, color='#222', alpha=0.5)

# === 右侧分析视口 (坐标轴全回归) ===
ax_cloud = fig.add_axes([0.68, 0.65, 0.25, 0.25])
ax_cloud.set_facecolor('#080808')
ax_cloud.set_title("ALETHEIA CLOUD (P-Space)", color='#00FFFF', fontsize=8, loc='left')
for s in ['bottom', 'top', 'right', 'left']: ax_cloud.spines[s].set_color('#333')
cloud_scatter, = ax_cloud.plot([], [], 'o', color='#00FFFF', markersize=1, alpha=0.3)
ax_cloud.set_xlim(0, 1); ax_cloud.set_ylim(0, 1)
ax_cloud.tick_params(colors='gray', labelsize=7)

ax_ent = fig.add_axes([0.68, 0.28, 0.25, 0.25])
ax_ent.set_facecolor('#080808')
ax_ent.set_title("H - ENTROPY (Bits)", color='#FF00FF', fontsize=8, loc='left')
for s in ['bottom', 'top', 'right', 'left']: ax_ent.spines[s].set_color('#333')
ent_line, = ax_ent.plot([], [], color='#FF00FF', lw=1.5)
ax_ent.set_xlim(0, 100); ax_ent.set_ylim(0, 7)
ax_ent.tick_params(colors='gray', labelsize=7)
ax_ent.grid(True, color='#222', alpha=0.5)

# 底端数字流
hex_text = fig.text(0.08, 0.08, "", color='#00FF00', fontfamily='monospace', fontsize=9, alpha=0.8)
info_text = fig.text(0.05, 0.95, "", color='yellow', fontfamily='monospace', fontsize=8)

btn = Button(plt.axes([0.75, 0.1, 0.1, 0.04]), 'PLAY/PAUSE', color='#151515', hovercolor='#333300')
btn.label.set_color('yellow')
btn.on_clicked(lambda e: setattr(universe, 'paused', not universe.paused))

stream = sd.OutputStream(channels=2, callback=audio_callback, samplerate=universe.sample_rate)
stream.start()
wire_container = [None]

def animate(i):
    universe.update()
    
    # 轨迹、波形、散点、熵值更新
    pa, pb = np.array(universe.path_a), np.array(universe.path_b)
    if len(pa) > 1:
        line_a, = ax_main.plot(pa[-150:, 0], pa[-150:, 1], pa[-150:, 2], color='#00FFFF', lw=2, alpha=0.8)
        for l in ax_main.get_lines()[:-1]: l.remove()
    
    if len(universe.wave_buffer) > 0:
        wave_line.set_data(range(len(universe.wave_buffer)), list(universe.wave_buffer))
    
    if len(universe.cloud_buffer) > 0:
        cb = np.array(list(universe.cloud_buffer))
        cloud_scatter.set_data(cb[:, 0], cb[:, 1])
    
    h = 0
    if len(universe.cloud_buffer) > 30:
        data = np.array(list(universe.cloud_buffer))
        hist, _, _ = np.histogram2d(data[:,0], data[:,1], bins=10, range=[[0,1],[0,1]])
        probs = hist.flatten() / len(data); probs = probs[probs > 0]
        h = -np.sum(probs * np.log2(probs))
    universe.entropy_history.append(h)
    ent_line.set_data(range(len(universe.entropy_history)), list(universe.entropy_history))
    
    hex_text.set_text(f">>> ALETHEIA_STREAM: {universe.last_echo_hex}")
    info_text.set_text(f" [ EXTRA-VIBRATIONAL ECHO ]  T: {universe.effective_t}\n"
                       f" FREQ (Hz): A:{universe.current_freq_a:.1f} / B:{universe.current_freq_b:.1f}\n"
                       f" ENTROPY: {h:.4f} bits")

    ax_main.view_init(elev=20, azim=i*0.4)
    ax_main.set_xlim(-7, 7); ax_main.set_ylim(-7, 7); ax_main.set_zlim(-7, 7)
    
    if not universe.paused and universe.effective_t % 4 == 0:
        if wire_container[0]: wire_container[0].remove()
        phi, theta = np.linspace(0, 2*np.pi, 20), np.linspace(0, 2*np.pi, 20)
        PH, TH = np.meshgrid(phi, theta); R = universe.current_R
        X = np.cos(5*PH)*(R+np.cos(5*TH)); Y = np.sin(5*PH)*(R+np.cos(5*TH)); Z = np.sin(5*TH)
        wire_container[0] = ax_main.plot_wireframe(X, Y, Z, color='yellow', lw=0.2, alpha=0.08)

ani = FuncAnimation(fig, animate, interval=16, cache_frame_data=False)
plt.show()
stream.stop()