%% 天线仿真结果专业分析脚本
% 分析 S11（回波损耗）和远场方向图
% 使用方法: 在 MATLAB 中打开此文件，点击 "运行"
% 或命令行: matlab -batch "run('analyze_results.m')"

clear; clc; close all;
fprintf('=== 天线仿真结果分析 ===\n\n');

%% 1. 读取数据
results_dir = fileparts(fileparts(mfilename('fullpath')));  % 上级目录 = 项目根目录
results_dir = fullfile(results_dir, 'results');

% 读取 S11_dB (已修正: 使用 dB(S(1,1)) 幅度数据)
opts = detectImportOptions(fullfile(results_dir, 'S11_dB.csv'));
opts.VariableNamingRule = 'preserve';
s11_data = readtable(fullfile(results_dir, 'S11_dB.csv'), opts);
freq = s11_data{:, 'Freq [GHz]'};           % 频率 GHz
s11_dB = s11_data{:, 'dB(S(1,1)) (Real)'};  % S11 幅度 (dB)，已经是 dB 值

% 读取方向图
opts = detectImportOptions(fullfile(results_dir, 'farfield.csv'));
opts.VariableNamingRule = 'preserve';
ff_data = readtable(fullfile(results_dir, 'farfield.csv'), opts);
theta = ff_data{:, 'Theta [deg]'};  % Theta 角度
phi   = ff_data{:, 'Phi [deg]'};    % Phi 角度
gain_real = ff_data{:, 'GainTotal (Real)'};
gain_imag = ff_data{:, 'GainTotal (Imag)'};
gain_lin = sqrt(gain_real.^2 + gain_imag.^2);
gain_dB = 10 * log10(gain_lin + eps);  % GainTotal 已是功率增益，直接取 dB

%% ========================
%  2. S11 分析
%% ========================
fprintf('【S11 回波损耗分析】\n');

% 找到谐振点（S11 dB 最小值）
[s11_min_dB, idx_min] = min(s11_dB);
freq_resonant = freq(idx_min);

fprintf('  谐振频率: %.4f GHz\n', freq_resonant);
fprintf('  谐振点 S11: %.2f dB\n', s11_min_dB);

% -10 dB 带宽计算
below_10dB = s11_dB <= -10;
if any(below_10dB)
    bw_points = find(below_10dB);
    bw_start = freq(bw_points(1));
    bw_end   = freq(bw_points(end));
    bandwidth = bw_end - bw_start;
    fractional_bw = bandwidth / freq_resonant * 100;
    fprintf('  -10 dB 带宽: %.3f GHz (%.1f%%)\n', bandwidth, fractional_bw);
    fprintf('  带宽范围: %.3f ~ %.3f GHz\n', bw_start, bw_end);
else
    fprintf('  -10 dB 带宽: 无 (S11 未低于 -10 dB)\n');
end

% VSWR（从 dB 幅度反推）
% |S11|_linear = 10^(S11_dB / 20)
mag_gamma = 10.^(s11_dB / 20);
vswr = (1 + mag_gamma) ./ (1 - mag_gamma);
vswr_res = vswr(idx_min);
fprintf('  谐振点 VSWR: %.2f\n\n', vswr_res);

% --- S11 曲线图 ---
figure('Name', 'S11 分析', 'Position', [100, 100, 1200, 500]);

subplot(1,2,1);
plot(freq, s11_dB, 'b-', 'LineWidth', 2); hold on;
plot(freq_resonant, s11_min_dB, 'ro', 'MarkerSize', 10, 'LineWidth', 2);
yline(-10, 'r--', 'LineWidth', 1.5);
grid on; xlabel('频率 (GHz)'); ylabel('S_{11} (dB)');
title('S_{11} 回波损耗');
legend('S_{11}', sprintf('谐振点: %.3f GHz (%.1f dB)', freq_resonant, s11_min_dB), '-10 dB 线', ...
    'Location', 'best');
xlim([min(freq), max(freq)]);

subplot(1,2,2);
plot(freq, vswr, 'b-', 'LineWidth', 2); hold on;
plot(freq_resonant, vswr_res, 'ro', 'MarkerSize', 10, 'LineWidth', 2);
yline(2, 'r--', 'VSWR=2', 'LineWidth', 1.5);
yline(1.5, 'g--', 'VSWR=1.5', 'LineWidth', 1.5);
grid on; xlabel('频率 (GHz)'); ylabel('VSWR');
title('电压驻波比');
legend('VSWR', sprintf('谐振点: %.2f', vswr_res), 'Location', 'best');

%% ========================
%  3. 方向图分析（2D 切片）
%% ========================
fprintf('【方向图分析】\n');

% 获取唯一的 Phi 和 Theta 角
unique_phi = unique(phi);
unique_theta = unique(theta);
n_phi = length(unique_phi);
n_theta = length(unique_theta);

% 将数据重塑为矩阵 [Theta x Phi]
gain_2d = reshape(gain_dB, [n_theta, n_phi]);
theta_2d = reshape(theta, [n_theta, n_phi]);
phi_2d = reshape(phi, [n_theta, n_phi]);

% 找到主瓣方向
[max_gain_dB, max_idx] = max(gain_dB);
fprintf('  最大增益: %.2f dB\n', max_gain_dB);
fprintf('  最大增益方向: Theta=%.1f°, Phi=%.1f°\n', ...
    theta(max_idx), phi(max_idx));

% E 面和 H 面切片
phi_idx_E = find(abs(unique_phi) < 1 | abs(abs(unique_phi) - 180) < 1, 1);  % Phi=0° (E-plane)
phi_idx_H = find(abs(abs(unique_phi) - 90) < 1, 1);  % Phi=90° (H-plane)

if isempty(phi_idx_E), phi_idx_E = 1; end
if isempty(phi_idx_H), phi_idx_H = round(n_phi/4); end

e_plane_gain = gain_2d(:, phi_idx_E);
h_plane_gain = gain_2d(:, phi_idx_H);
e_plane_theta = theta_2d(:, phi_idx_E);
h_plane_theta = theta_2d(:, phi_idx_H);

% 归一化
e_plane_norm = e_plane_gain - max(e_plane_gain);
h_plane_norm = h_plane_gain - max(h_plane_gain);

fprintf('  E-面 (Phi=%.0f°) 最大增益: %.2f dB\n', ...
    unique_phi(phi_idx_E), max(e_plane_gain));
fprintf('  H-面 (Phi=%.0f°) 最大增益: %.2f dB\n\n', ...
    unique_phi(phi_idx_H), max(h_plane_gain));

% --- 2D 极坐标方向图 ---
figure('Name', '方向图 2D 切片', 'Position', [100, 100, 1200, 500]);

subplot(1,2,1);
polarplot(deg2rad(e_plane_theta), e_plane_norm + 40, 'b-', 'LineWidth', 2); hold on;
polarplot(deg2rad(h_plane_theta), h_plane_norm + 40, 'r--', 'LineWidth', 2);
legend('E-面 (φ=0°)', 'H-面 (φ=90°)', 'Location', 'northeast');
title(sprintf('归一化方向图 @ %.2f GHz', freq_resonant));
rlim([0, 45]);
rticklabels({'','-40 dB','-30 dB','-20 dB','-10 dB','0 dB'});

subplot(1,2,2);
polarplot(deg2rad(e_plane_theta), max(e_plane_gain) - 40 + e_plane_norm, 'b-', 'LineWidth', 2); hold on;
polarplot(deg2rad(h_plane_theta), max(h_plane_gain) - 40 + h_plane_norm, 'r--', 'LineWidth', 2);
legend('E-面 (φ=0°)', 'H-面 (φ=90°)', 'Location', 'northeast');
title(sprintf('实际增益方向图 @ %.2f GHz', freq_resonant));
rlim([max_gain_dB - 40, max_gain_dB + 2]);
rticklabels({'',sprintf('%.0f dB',max_gain_dB-30),sprintf('%.0f dB',max_gain_dB-20),...
    sprintf('%.0f dB',max_gain_dB-10),sprintf('%.0f dB',max_gain_dB)});

%% --- 3D 方向图 ---
figure('Name', '3D 方向图', 'Position', [100, 100, 800, 600]);

% 重塑到球坐标网格
Theta_grid = reshape(theta, [n_theta, n_phi]) * pi/180;
Phi_grid = reshape(phi, [n_phi, n_theta])' * pi/180;
Gain_grid = reshape(gain_dB, [n_theta, n_phi]);

% 3D 球面方向图
[X, Y, Z] = sph2cart(Phi_grid, pi/2 - Theta_grid, Gain_grid - min(Gain_grid(:)) + 3);
surf(X, Y, Z, Gain_grid, 'EdgeColor', 'none', 'FaceAlpha', 0.9);
colormap(jet);
colorbar; caxis([max_gain_dB - 30, max_gain_dB]);
title(sprintf('3D 增益方向图 @ %.2f GHz', freq_resonant));
xlabel('X'); ylabel('Y'); zlabel('Z');
axis equal; grid on;
view(45, 30);
lighting gouraud; light('Position', [1, 1, 1]);

%% ========================
%  4. 导出分析报告
%% ========================
fprintf('=== 分析完成 ===\n');
fprintf('  结果图表已显示。\n');
fprintf('  图表将保存至: %s\n', results_dir);

% 保存图表
saveas(figure(1), fullfile(results_dir, 'S11_analysis.png'));
saveas(figure(2), fullfile(results_dir, 'patterns_2d.png'));
saveas(figure(3), fullfile(results_dir, 'pattern_3d.png'));
fprintf('  图表已保存为 PNG。\n\n');

%% 保存分析摘要
summary_file = fullfile(results_dir, 'analysis_summary.txt');
fid = fopen(summary_file, 'w');
fprintf(fid, '=== 天线仿真分析摘要 ===\n');
fprintf(fid, '分析日期: %s\n\n', datestr(now));
fprintf(fid, '--- S11 参数 ---\n');
fprintf(fid, '谐振频率: %.4f GHz\n', freq_resonant);
fprintf(fid, '谐振点 S11: %.2f dB\n', s11_min_dB);
fprintf(fid, '-10 dB 带宽: %.3f GHz\n', bandwidth);
fprintf(fid, 'VSWR: %.2f\n\n', vswr_res);
fprintf(fid, '--- 方向图参数 ---\n');
fprintf(fid, '最大增益: %.2f dB\n', max_gain_dB);
fprintf(fid, 'E-面最大增益: %.2f dB\n', max(e_plane_gain));
fprintf(fid, 'H-面最大增益: %.2f dB\n\n', max(h_plane_gain));
fclose(fid);

fprintf('  分析摘要已保存至: %s\n', summary_file);
