import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import datetime
import os
import sys
import struct
import hashlib
from stl import mesh

# =================================================================
# 【11D 动力学实验室：广域全视口版 V6.0 - 混沌熵提取版】
# 1. 熵提取器：利用浮点数末位舍入误差产生的计算噪声生成随机序列。
# 2. 自激反馈：提取的随机熵实时转化为微扰算子，干预粒子运动轨迹。
# 3. 严禁删减：保留 V5.0 所有 STL 导出、UI 布局及物理模拟功能。
# =================================================================

class ProInteractiveLab:
    def __init__(self):
        self.dt = 0.0075
        self.r0 = 1.6
        self.breath_amp = 0.45
        self.omega = 1.55
        self.paused = True  
        self.effective_t = 0  
        
        self.pos_a = np.array([1.0, 0.0, 0.0])
        self.pos_b = np.array([1.001, 0.0, 0.0])
        self.vel_a = np.array([0.0, 1.85, 0.35])
        self.vel_b = np.array([0.0, 1.85, 0.35])
        
        self.path_a, self.path_b = [], []
        self.vibration_sense = 1.35
        self.current_R = self.r0
        self.gravity_const = -4.2 
        
        # --- 混沌随机数模块数据 ---
        self.last_entropy_hex = "0" * 64
        self.micro_perturbation = 0.0

    def get_chaos_entropy(self):
        """
        核心逻辑：提取 11 维相空间的浮点数末位噪声比特。
        不依赖外部输入，只依赖计算本身的非线性损耗。
        """
        raw_bits = b""
        for p in [self.pos_a, self.pos_b, self.vel_a, self.vel_b]:
            for val in p:
                # 提取浮点数的 64 位原始内存数据
                raw_bits += struct.pack('d', val)
        
        # 使用 SHA-256 搅拌这些噪声比特，消除任何残余的统计规律
        full_hash = hashlib.sha256(raw_bits).hexdigest()
        self.last_entropy_hex = full_hash
        
        # 将哈希值转化为 0-1 之间的浮点数作为反馈微扰
        # 取哈希最后 8 位转化为整数，映射到 [-0.01, 0.01] 的极小扰动
        entropy_val = int(full_hash[-8:], 16) / 0xFFFFFFFF
        self.micro_perturbation = (entropy_val - 0.5) * 0.02
        return full_hash

    def calculate_force(self, p_pos, t, v_vec):
        r_mag = np.linalg.norm(p_pos) + 1e-9
        # 注入混沌反馈：微扰项直接干预引力常数的瞬时表现
        g_eff = self.gravity_const + self.micro_perturbation
        f_macro = g_eff * p_pos / (r_mag**2.9)
        
        dynamic_mod = 1.0 + 0.65 * np.sin(self.omega * t * 0.1)
        f_cy = self.vibration_sense * dynamic_mod * np.array([
            np.sin(7 * p_pos[0]),
            np.cos(7 * p_pos[1]),
            np.sin(7 * p_pos[2] + np.cos(p_pos[0]))
        ])
        return f_macro + f_cy

    def update(self):
        if not self.paused:
            self.effective_t += 1 
            t = self.effective_t
            
            # 每步更新提取一次混沌熵
            self.get_chaos_entropy()
            
            for p, v, path in zip([self.pos_a, self.pos_b], [self.vel_a, self.vel_b], [self.path_a, self.path_b]):
                f = self.calculate_force(p, t, v)
                v += f * self.dt
                p += v * self.dt
                path.append(p.copy())
            self.current_R = self.r0 + self.breath_amp * np.sin(self.omega * t * 0.1)

    def save_to_stl(self):
        if len(self.path_a) < 5 and len(self.path_b) < 5: 
            print("Insufficient data to save.")
            return
        filename = f"manifold_V6_Chaos_{datetime.datetime.now().strftime('%H%M%S')}.stl"
        radius = 0.015  
        segments = 8    
        with open(filename, 'w') as f:
            f.write(f"solid {filename}\n")
            def write_tube(path_data):
                pts = np.array(path_data)
                angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
                for i in range(len(pts) - 1):
                    p0, p1 = pts[i], pts[i+1]
                    tangent = p1 - p0
                    t_norm = np.linalg.norm(tangent)
                    if t_norm < 1e-8: continue
                    T = tangent / t_norm
                    U = np.array([1, 0, 0]) if abs(T[0]) < 0.9 else np.array([0, 1, 0])
                    V = np.cross(T, U)
                    V /= np.linalg.norm(V)
                    W = np.cross(T, V)
                    ring_curr = [p0 + radius * (np.cos(a) * V + np.sin(a) * W) for a in angles]
                    ring_next = [p1 + radius * (np.cos(a) * V + np.sin(a) * W) for a in angles]
                    for j in range(segments):
                        nj = (j + 1) % segments
                        for tri in [(ring_curr[j], ring_next[j], ring_curr[nj]),
                                    (ring_next[j], ring_next[nj], ring_curr[nj])]:
                            f.write("facet normal 0 0 0\nouter loop\n")
                            for v in tri:
                                f.write(f"vertex {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                            f.write("endloop\nendfacet\n")
            if len(self.path_a) >= 2: write_tube(self.path_a)
            if len(self.path_b) >= 2: write_tube(self.path_b)
            f.write(f"endsolid {filename}\n")
        print(f"Chaos Trajectory STL saved: {filename}")

# --- 渲染逻辑与 UI 布局 ---
universe = ProInteractiveLab()
plt.rcParams['toolbar'] = 'None'
fig = plt.figure(facecolor='black', figsize=(16, 9))

try:
    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()
except:
    pass

ax = fig.add_axes([-0.25, -0.25, 1.5, 1.5], projection='3d')
ax.set_facecolor('black')
ax.set_axis_off()
ax.margins(0)

self_limit = [8.0]

def on_scroll(event):
    step = self_limit[0] * 0.1
    if event.button == 'up': self_limit[0] -= step
    elif event.button == 'down': self_limit[0] += step
    self_limit[0] = max(self_limit[0], 1.5)

fig.canvas.mpl_connect('scroll_event', on_scroll)

line_a, = ax.plot([], [], [], color='#00FFFF', lw=2.2, alpha=0.9, zorder=10)
line_b, = ax.plot([], [], [], color='#FF00FF', lw=1.2, alpha=0.7, zorder=9)
head_a, = ax.plot([], [], [], 'wo', markersize=5, zorder=15)
head_b, = ax.plot([], [], [], 'yo', markersize=4, zorder=15)

info_text = fig.text(0.01, 0.98, "", color='yellow', fontfamily='monospace', verticalalignment='top', fontsize=9, alpha=0.9)
tag_a = ax.text(0, 0, 0, "STRING A", color='#00FFFF', fontweight='bold', fontsize=8)
tag_b = ax.text(0, 0, 0, "STRING B", color='#FF00FF', fontweight='bold', fontsize=8)

btn_style = dict(color='#222222', hovercolor='#444400') 

ax_button = plt.axes([0.45, 0.02, 0.1, 0.04], frameon=False)
btn = Button(ax_button, 'PLAY', **btn_style)
btn.label.set_color('yellow')

ax_save = plt.axes([0.91, 0.95, 0.08, 0.03], frameon=False)
btn_save = Button(ax_save, 'SAVE', **btn_style)
btn_save.label.set_color('yellow')

ax_load = plt.axes([0.82, 0.95, 0.08, 0.03], frameon=False)
btn_load = Button(ax_load, 'LOAD', **btn_style)
btn_load.label.set_color('yellow')

ax_exit = plt.axes([0.91, 0.02, 0.08, 0.03], frameon=False)
btn_exit = Button(ax_exit, 'EXIT', **btn_style)
btn_exit.label.set_color('red')

def toggle_pause(event):
    universe.paused = not universe.paused
    btn.label.set_text('PLAY' if universe.paused else 'PAUSE')

def save_stl(event):
    universe.save_to_stl()

def load_path(event):
    stls = [f for f in os.listdir('.') if f.endswith('.stl')]
    if not stls: return
    latest_stl = max(stls, key=os.path.getctime)
    try:
        your_mesh = mesh.Mesh.from_file(latest_stl)
        centers = np.mean(your_mesh.vectors, axis=1)
        raw_recovered = []
        step_size = 16 
        for i in range(0, len(centers), step_size):
            chunk = centers[i:i+step_size]
            if len(chunk) > 0: raw_recovered.append(np.mean(chunk, axis=0))
        if not raw_recovered: return
        final_path_a, final_path_b = [], []
        current_target = final_path_a
        threshold = 1.0 
        for i in range(len(raw_recovered)):
            if i > 0:
                dist = np.linalg.norm(raw_recovered[i] - raw_recovered[i-1])
                if dist > threshold: current_target = final_path_b
            current_target.append(raw_recovered[i])
        if final_path_a:
            universe.path_a = final_path_a
            universe.pos_a = final_path_a[-1].copy()
            if len(final_path_a) > 1:
                universe.vel_a = (final_path_a[-1] - final_path_a[-2]) / universe.dt
            universe.effective_t = len(final_path_a)
        if final_path_b:
            universe.path_b = final_path_b
            universe.pos_b = final_path_b[-1].copy()
            if len(final_path_b) > 1:
                universe.vel_b = (final_path_b[-1] - final_path_b[-2]) / universe.dt
    except Exception as e:
        print(f"Load Error: {e}")

def exit_lab(event):
    plt.close('all')
    sys.exit()

btn.on_clicked(toggle_pause)
btn_save.on_clicked(save_stl)
btn_load.on_clicked(load_path)
btn_exit.on_clicked(exit_lab)

wire_container = [None]

def animate(i):
    universe.update()
    t_display = universe.effective_t
    
    bbox = fig.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    aspect_ratio = bbox.width / bbox.height
    
    ax.dist = 6.8 
    ax.set_box_aspect((aspect_ratio, 1, 1))

    lim = self_limit[0]
    ax.set_xlim([-lim * aspect_ratio, lim * aspect_ratio])
    ax.set_ylim([-lim, lim])
    ax.set_zlim([-lim, lim])

    pa, pb = np.array(universe.path_a), np.array(universe.path_b)
    if len(pa) > 1:
        line_a.set_data(pa[:, 0], pa[:, 1]); line_a.set_3d_properties(pa[:, 2])
        head_a.set_data([universe.pos_a[0]], [universe.pos_a[1]]); head_a.set_3d_properties([universe.pos_a[2]])
        tag_a.set_position((universe.pos_a[0], universe.pos_a[1]))
        tag_a.set_3d_properties(universe.pos_a[2] + 0.4)

    if len(pb) > 1:
        line_b.set_data(pb[:, 0], pb[:, 1]); line_b.set_3d_properties(pb[:, 2])
        head_b.set_data([universe.pos_b[0]], [universe.pos_b[1]]); head_b.set_3d_properties([universe.pos_b[2]])
        tag_b.set_position((universe.pos_b[0], universe.pos_b[1]))
        tag_b.set_3d_properties(universe.pos_b[2] - 0.4)

    v_a = np.linalg.norm(universe.vel_a)
    v_b = np.linalg.norm(universe.vel_b)
    current_azim = (t_display * 0.35) % 360
    
    # 仪表盘增加混沌随机数监控
    dashboard = (
        f" [ 11D MANIFOLD OBSERVATORY ]\n"
        f" -----------------------------\n"
        f" SYS STATUS: {'PAUSED' if universe.paused else 'RUNNING'}\n"
        f" TIME STEP : {t_display}\n"
        f" GEOMETRY R: {universe.current_R:.4f}\n"
        f" G-CONSTANT: {universe.gravity_const + universe.micro_perturbation:.5f}\n\n"
        f" STRING A (CYAN):\n"
        f"  COORDS  : [{universe.pos_a[0]:.2f}, {universe.pos_a[1]:.2f}, {universe.pos_a[2]:.2f}]\n"
        f"  VELOCITY: {v_a:.3f} u/s\n\n"
        f" STRING B (MAGENTA):\n"
        f"  COORDS  : [{universe.pos_b[0]:.2f}, {universe.pos_b[1]:.2f}, {universe.pos_b[2]:.2f}]\n"
        f"  VELOCITY: {v_b:.3f} u/s\n\n"
        f" VIEWPORT :\n"
        f"  SCALE   : {lim:.1f}x\n"
        f"  AZIMUTH : {current_azim:.1f}°"
        f"\n\n"
        f" CHAOS ENTROPY (SHA-256):\n"
        f" {universe.last_entropy_hex[:32]}...\n\n"
    )
    info_text.set_text(dashboard)

    if not universe.paused:
        if t_display % 3 == 0:
            if wire_container[0]: wire_container[0].remove()
            
            phi = np.linspace(0, 2 * np.pi, 45)
            theta = np.linspace(0, 2 * np.pi, 45)
            PHI, THETA = np.meshgrid(phi, theta)
            
            R = universe.current_R
            X = np.cos(5 * PHI) * (R + np.cos(5 * THETA))
            Y = np.sin(5 * PHI) * (R + np.cos(5 * THETA))
            Z = np.sin(5 * THETA)
            
            for p_pos in [universe.pos_a, universe.pos_b]:
                dist_sq = (X - p_pos[0])**2 + (Y - p_pos[1])**2 + (Z - p_pos[2])**2 + 1e-6
                ripple = 0.25 / (dist_sq + 0.5) 
                X -= ripple * (X - p_pos[0])
                Y -= ripple * (Y - p_pos[1])
                Z -= ripple * (Z - p_pos[2])
            
            wire_container[0] = ax.plot_wireframe(X, Y, Z, color='yellow', linewidth=0.4, alpha=0.15, zorder=1)
        ax.view_init(elev=ax.elev, azim=ax.azim + 0.35)
    
    return line_a, line_b, info_text

ani = FuncAnimation(fig, animate, frames=2000, blit=False, interval=16)
plt.show()