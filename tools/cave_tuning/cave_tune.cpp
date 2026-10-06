// Автономный инструмент для подбора параметров генератора пещер (World_Generator::cave_density_at).
// Использует ТОТ ЖЕ noise3_XZBeforeY/fbm3 и ту же схему сида, что и движок, так что результат
// напрямую переносится в src/world/World_Generator.cpp. Собирается отдельно от движка — не
// тянет Chunk/Renderer/OpenGL, только сама библиотека шума. См. build.sh и README.md рядом.
//
// Режимы:
//   sweep                         — таблица связности для набора кандидатов (freq, band)
//   slice  <freq> <band> [y]      — ASCII-срез сверху (XZ) на заданной высоте
//   vslice <freq> <band> [z]      — ASCII-срез сбоку (XY) на заданном Z
//
// band — это kTunnelBand из World_Generator.cpp; freq — частота fbm3 для n1/n2.
// Изменили здесь — перенесите те же два числа в cave_density_at().

#include "OpenSimplex2S.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <deque>
#include <string>

static uint64_t splitmix64(uint64_t value) {
    value += 0x9E3779B97F4A7C15ULL;
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9ULL;
    value = (value ^ (value >> 27)) * 0x94D049BB133111EBULL;
    return value ^ (value >> 31);
}
static uint32_t derive_seed(uint32_t world_seed, uint64_t salt) {
    return static_cast<uint32_t>(splitmix64(static_cast<uint64_t>(world_seed) ^ salt) ^
                                 (splitmix64(static_cast<uint64_t>(world_seed) ^ salt) >> 32));
}

static OpenSimplexEnv* g_env;
static OpenSimplexGradients* g_grad;

static double noise3(double x, double y, double z) {
    return noise3_XZBeforeY(g_env, g_grad, x, y, z);
}

// Точная копия World_Generator::fbm3.
static double fbm3(double x, double y, double z, int octaves, double frequency,
                    double lacunarity, double gain) {
    double sum = 0.0, amplitude = 1.0, amplitude_sum = 0.0;
    for (int i = 0; i < octaves; ++i) {
        sum += noise3(x * frequency, y * frequency, z * frequency) * amplitude;
        amplitude_sum += amplitude;
        frequency *= lacunarity;
        amplitude *= gain;
    }
    return amplitude_sum > 0.0 ? sum / amplitude_sum : 0.0;
}

static double clamp01(double v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

// Тоннельный сигнал — то же самое, что `tunnel` в cave_density_at. y_stretch зафиксирован
// на 1.4, как в движке (World_Y * 1.4 перед fbm3); при желании поменяйте тут же.
static double tunnel_at(double x, double y, double z, double freq, double band) {
    const double n1 = fbm3(x, y * 1.4, z, 3, freq, 2.0, 0.5);
    const double n2 = fbm3(x + 4096.0, y * 1.4, z - 4096.0, 3, freq, 2.0, 0.5);
    const double band1 = clamp01(1.0 - std::fabs(n1) / band);
    const double band2 = clamp01(1.0 - std::fabs(n2) / band);
    return band1 * band2;
}

// 6-связный flood fill по вырезанному объёму. Возвращает % вырезанного объёма, число
// компонент и долю самой большой компоненты — то есть, грубо говоря, "это один протяжённый
// ход или облако несвязанного мусора".
static void evaluate(double freq, double band, int SX, int SY, int SZ, double threshold,
                      double& carved_pct, int& n_components, double& largest_share_pct) {
    std::vector<uint8_t> carved(static_cast<size_t>(SX) * SY * SZ, 0);
    auto idx = [&](int x, int y, int z) { return (static_cast<size_t>(x) * SY + y) * SZ + z; };

    long carved_count = 0;
    for (int x = 0; x < SX; ++x)
        for (int y = 0; y < SY; ++y)
            for (int z = 0; z < SZ; ++z)
                if (tunnel_at(x, y, z, freq, band) > threshold) { carved[idx(x,y,z)] = 1; ++carved_count; }

    carved_pct = 100.0 * carved_count / (static_cast<double>(SX) * SY * SZ);

    // Один проход flood fill: считает и число компонент, и размер каждой, откуда берём largest.
    std::vector<uint8_t> visited(carved.size(), 0);
    long largest = 0;
    n_components = 0;
    for (int x = 0; x < SX; ++x)
        for (int y = 0; y < SY; ++y)
            for (int z = 0; z < SZ; ++z) {
                size_t start = idx(x, y, z);
                if (!carved[start] || visited[start]) continue;
                ++n_components;
                long size = 0;
                std::deque<int> qx, qy, qz;
                qx.push_back(x); qy.push_back(y); qz.push_back(z);
                visited[start] = 1;
                while (!qx.empty()) {
                    int cx=qx.front(); qx.pop_front();
                    int cy=qy.front(); qy.pop_front();
                    int cz=qz.front(); qz.pop_front();
                    ++size;
                    static const int dxs[6]={1,-1,0,0,0,0}, dys[6]={0,0,1,-1,0,0}, dzs[6]={0,0,0,0,1,-1};
                    for (int d=0; d<6; ++d) {
                        int nx=cx+dxs[d], ny=cy+dys[d], nz=cz+dzs[d];
                        if (nx<0||nx>=SX||ny<0||ny>=SY||nz<0||nz>=SZ) continue;
                        size_t ni = idx(nx,ny,nz);
                        if (carved[ni] && !visited[ni]) { visited[ni]=1; qx.push_back(nx); qy.push_back(ny); qz.push_back(nz); }
                    }
                }
                largest = std::max(largest, size);
            }
    largest_share_pct = carved_count > 0 ? (100.0 * largest / carved_count) : 0.0;
}

static void run_sweep() {
    printf("%-7s %-7s %9s %8s %14s\n", "freq", "band", "carved%", "#comp", "largest_share%");
    struct Case { double freq, band; };
    std::vector<Case> cases = {
        {0.020, 0.045}, // текущее значение движка "как было" — для сравнения
        {0.020, 0.12}, {0.020, 0.14}, {0.020, 0.16}, {0.020, 0.18}, {0.020, 0.22},
        {0.018, 0.14}, {0.018, 0.16}, {0.018, 0.18},
        {0.016, 0.15}, {0.014, 0.22},
    };
    for (auto& c : cases) {
        double carved_pct, largest_share_pct; int n_components;
        evaluate(c.freq, c.band, 96, 48, 96, 0.5, carved_pct, n_components, largest_share_pct);
        printf("%-7.3f %-7.3f %8.2f%% %8d %13.1f%%\n", c.freq, c.band, carved_pct, n_components, largest_share_pct);
    }
    printf("\ncarved%% — доля вырезанного объёма. largest_share%% — какая часть ВСЕХ вырезанных\n"
           "вокселей лежит в одной связной системе (высокий %% = настоящие протяжённые ходы,\n"
           "низкий %% = раздробленные отдельные \"дырки\", тот самый исходный баг при band=0.045).\n");
}

static void run_slice(double freq, double band, int fixedY) {
    const int SX = 110, SZ = 110;
    for (int x = 0; x < SX; ++x) {
        std::string row;
        for (int z = 0; z < SZ; ++z) row += (tunnel_at(x, fixedY, z, freq, band) > 0.5) ? '#' : '.';
        printf("%s\n", row.c_str());
    }
}

static void run_vslice(double freq, double band, int fixedZ) {
    const int SX = 110, SY = 48;
    for (int y = SY - 1; y >= 0; --y) {
        std::string row;
        for (int x = 0; x < SX; ++x) row += (tunnel_at(x, y, fixedZ, freq, band) > 0.5) ? '#' : '.';
        printf("%s\n", row.c_str());
    }
}

int main(int argc, char** argv) {
    g_env = initOpenSimplex();
    g_grad = newOpenSimplexGradients(g_env, derive_seed(1327, 0x09)); // Config::seed, соль 0x09 — как m_caves

    const std::string mode = argc > 1 ? argv[1] : "sweep";
    if (mode == "sweep") {
        run_sweep();
    } else if (mode == "slice" && argc >= 4) {
        run_slice(atof(argv[2]), atof(argv[3]), argc > 4 ? atoi(argv[4]) : 20);
    } else if (mode == "vslice" && argc >= 4) {
        run_vslice(atof(argv[2]), atof(argv[3]), argc > 4 ? atoi(argv[4]) : 20);
    } else {
        fprintf(stderr, "Использование:\n"
                        "  cave_tune sweep\n"
                        "  cave_tune slice  <freq> <band> [y=20]\n"
                        "  cave_tune vslice <freq> <band> [z=20]\n");
        return 1;
    }
    return 0;
}
