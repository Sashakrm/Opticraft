// Автономный офскрин-тест (реальные GLFW+GLAD+OpenGL 3.3 core) — воспроизводит ТОЧНО ту же
// occlusion-query логику, что Renderer::render_chunks (issue_occlusion_query), и прогоняет её
// через несколько камер и несколько стратегий смещения бокса, чтобы проверить: колеблется ли
// результат запроса из кадра в кадр при АБСОЛЮТНО статичной камере. Если да — это не дрожание
// мыши, это структурный цикл "секция гасит сама себя → в следующем кадре её нечем перекрыть →
// снова видима → снова гасит себя…", и никакая точность/подбор magnitude смещения его не
// вылечит, лечится только сменой направления смещения (см. README.md рядом).
//
// См. README.md: как собрать и куда переносить числа, если решите потюнить дальше.

#include <glad/gl.h>
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <cstdio>
#include <cmath>
#include <vector>
#include <string>

static GLuint compile_shader(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetShaderInfoLog(s, sizeof(log), nullptr, log);
        fprintf(stderr, "Shader compile error: %s\n", log);
    }
    return s;
}
static GLuint link_program(const char* vs_src, const char* fs_src) {
    GLuint vs = compile_shader(GL_VERTEX_SHADER, vs_src);
    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fs_src);
    GLuint p = glCreateProgram();
    glAttachShader(p, vs); glAttachShader(p, fs);
    glLinkProgram(p);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetProgramInfoLog(p, sizeof(log), nullptr, log);
        fprintf(stderr, "Program link error: %s\n", log);
    }
    glDeleteShader(vs); glDeleteShader(fs);
    return p;
}

// Единичный куб 0..1 — байт-в-байт та же геометрия, что occlusion_cube в Renderer.cpp.
static const float kUnitCube[] = {
    0,0,0,  0,1,0,  0,1,1,   0,0,0,  0,1,1,  0,0,1,
    1,0,0,  1,1,1,  1,1,0,   1,0,0,  1,0,1,  1,1,1,
    0,0,0,  1,0,1,  1,0,0,   0,0,0,  0,0,1,  1,0,1,
    0,1,0,  1,1,0,  1,1,1,   0,1,0,  1,1,1,  0,1,1,
    0,0,0,  1,1,0,  1,0,0,   0,0,0,  0,1,0,  1,1,0,
    0,0,1,  1,0,1,  1,1,1,   0,0,1,  1,1,1,  0,1,1,
};

struct Box { glm::vec3 min, max; };

struct BiasStrategy {
    const char* name;
    float geo_bias;     // >0 = inset inward (shrink), <0 = expand outward (grow)
    float po_factor;    // glPolygonOffset factor
    float po_units;     // glPolygonOffset units
};

int main() {
    if (!glfwInit()) { fprintf(stderr, "glfwInit failed\n"); return 1; }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    glfwWindowHint(GLFW_DEPTH_BITS, 24);
    GLFWwindow* win = glfwCreateWindow(800, 600, "occlusion-test", nullptr, nullptr);
    if (!win) { fprintf(stderr, "glfwCreateWindow failed\n"); return 1; }
    glfwMakeContextCurrent(win);
    if (!gladLoadGL((GLADloadfunc)glfwGetProcAddress)) { fprintf(stderr, "gladLoadGL failed\n"); return 1; }

    GLuint solid_prog = link_program(
        "#version 330 core\nlayout(location=0) in vec3 aPos;\nuniform mat4 mvp;\nvoid main(){gl_Position=mvp*vec4(aPos,1.0);}\n",
        "#version 330 core\nout vec4 FragColor;\nvoid main(){FragColor=vec4(1.0);}\n");
    // Точная копия assets/shaders/occlusion_{vertex,fragment}.glsl проекта.
    GLuint occ_prog = link_program(
        "#version 330 core\nlayout (location = 0) in vec3 aPos;\nuniform mat4 model;\nuniform mat4 view;\nuniform mat4 projection;\nvoid main() {\n    gl_Position = projection * view * model * vec4(aPos, 1.0);\n}\n",
        "#version 330 core\nout vec4 FragColor;\nvoid main() {\n    FragColor = vec4(1.0);\n}\n");

    GLuint vao, vbo;
    glGenVertexArrays(1, &vao);
    glGenBuffers(1, &vbo);
    glBindVertexArray(vao);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(kUnitCube), kUnitCube, GL_STATIC_DRAW);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, (void*)0);
    glEnableVertexAttribArray(0);

    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);

    auto draw_box_solid = [&](const Box& b, const glm::mat4& vp) {
        glUseProgram(solid_prog);
        glm::mat4 model(1.0f);
        model = glm::translate(model, b.min);
        model = glm::scale(model, glm::max(b.max - b.min, glm::vec3(0.001f)));
        glm::mat4 mvp = vp * model;
        glUniformMatrix4fv(glGetUniformLocation(solid_prog, "mvp"), 1, GL_FALSE, &mvp[0][0]);
        glBindVertexArray(vao);
        glDrawArrays(GL_TRIANGLES, 0, 36);
    };

    // Точная копия схемы issue_occlusion_query: geo_bias>0 сжимает бокс внутрь (текущий
    // 2-й фикс), geo_bias<0 расширяет наружу (гипотеза "по умолчанию видимо").
    auto query_box = [&](const Box& b, const glm::mat4& view, const glm::mat4& proj,
                          const BiasStrategy& bias) -> bool {
        glUseProgram(occ_prog);
        glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);
        glDepthMask(GL_FALSE);
        glDisable(GL_CULL_FACE);
        glEnable(GL_POLYGON_OFFSET_FILL);
        glPolygonOffset(bias.po_factor, bias.po_units);

        const glm::vec3 bmin = b.min + glm::vec3(bias.geo_bias);
        const glm::vec3 bmax = b.max - glm::vec3(bias.geo_bias);
        glm::mat4 model(1.0f);
        model = glm::translate(model, bmin);
        model = glm::scale(model, glm::max(bmax - bmin, glm::vec3(0.001f)));
        glUniformMatrix4fv(glGetUniformLocation(occ_prog, "model"), 1, GL_FALSE, &model[0][0]);
        glUniformMatrix4fv(glGetUniformLocation(occ_prog, "view"), 1, GL_FALSE, &view[0][0]);
        glUniformMatrix4fv(glGetUniformLocation(occ_prog, "projection"), 1, GL_FALSE, &proj[0][0]);

        GLuint q;
        glGenQueries(1, &q);
        glBindVertexArray(vao);
        glBeginQuery(GL_ANY_SAMPLES_PASSED, q);
        glDrawArrays(GL_TRIANGLES, 0, 36);
        glEndQuery(GL_ANY_SAMPLES_PASSED);
        GLuint result = 0;
        glGetQueryObjectuiv(q, GL_QUERY_RESULT, &result); // blocking — fine for this offline test
        glDeleteQueries(1, &q);

        glDepthMask(GL_TRUE);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glDisable(GL_POLYGON_OFFSET_FILL);
        glEnable(GL_CULL_FACE);
        return result != 0;
    };

    const Box section{glm::vec3(0, 0, 0), glm::vec3(32, 8, 32)};
    const glm::mat4 proj = glm::perspective(glm::radians(70.0f), 800.0f / 600.0f, 0.1f, 1000.0f);

    struct CamCase { const char* name; glm::vec3 eye, forward; };
    const glm::vec3 box_center = (section.min + section.max) * 0.5f;
    auto pitch_forward = [](float pitch_deg) {
        const float p = glm::radians(pitch_deg);
        // yaw=0: forward starts along +Z, pitch rotates it toward -Y (looking down) as it
        // steepens — matches a player looking forward-and-down, not away from the section.
        return glm::normalize(glm::vec3(0.0f, std::sin(p), std::cos(p)));
    };
    auto eye_for = [&](float pitch_deg, float dist) {
        return box_center - pitch_forward(pitch_deg) * dist;
    };
    std::vector<CamCase> cams = {
        {"head_on   (взгляд в упор на переднюю грань, pitch=0)",  eye_for(0.0f, 25.0f),    pitch_forward(0.0f)},
        {"grazing   (скользящий взгляд вдоль стены)",             {100, 4, -0.5f}, glm::normalize(glm::vec3(-1.0f, 0.0f, 0.0f))},
        {"pitch=-60 (смотрю под углом вниз)",                     eye_for(-60.0f, 25.0f),  pitch_forward(-60.0f)},
        {"pitch=-75 (смотрю круче вниз)",                         eye_for(-75.0f, 25.0f),  pitch_forward(-75.0f)},
        {"pitch=-85 (почти прямо вниз)",                          eye_for(-85.0f, 25.0f),  pitch_forward(-85.0f)},
        {"pitch=-89.5 (прямо вниз, зазора нет)",                  eye_for(-89.5f, 25.0f),  pitch_forward(-89.5f)},
        {"pitch=-89.5, dist=10 (вниз, ближе)",                    eye_for(-89.5f, 10.0f),  pitch_forward(-89.5f)},
        {"стою на секции, смотрю под ноги (глаза +1.62 над верхом)",
                                                                   {16.0f, 8.0f + 1.62f, 15.9f}, pitch_forward(-89.5f)},
    };

    std::vector<BiasStrategy> strategies = {
        {"previous_broken (inset=+0.05, factor=0, units=+4)",     0.05f,  0.0f,  4.0f},
        {"previous_stronger_inset (inset=+0.05, factor=4, units=+8)", 0.05f, 4.0f, 8.0f},
        {"shipped (grow=-0.05, factor=-4, units=-8)",            -0.05f, -4.0f, -8.0f},
    };

    const int kFrames = 8;

    for (auto& cam : cams) {
        const glm::mat4 view = glm::lookAt(cam.eye, cam.eye + cam.forward, glm::vec3(0, 1, 0));
        const glm::mat4 vp = proj * view;
        printf("\n=== Камера: %s ===\n", cam.name);
        for (auto& strat : strategies) {
            bool visible = true; // стартовое состояние секции, как в движке (по умолчанию true)
            std::string seq;
            for (int f = 0; f < kFrames; ++f) {
                glViewport(0, 0, 800, 600);
                glClearColor(0, 0, 0, 0);
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
                if (visible) draw_box_solid(section, vp);
                visible = query_box(section, view, proj, strat);
                seq += visible ? '1' : '0';
            }
            bool saw01 = false, saw10 = false;
            for (size_t i = 1; i < seq.size(); ++i) {
                if (seq[i-1]=='0' && seq[i]=='1') saw01 = true;
                if (seq[i-1]=='1' && seq[i]=='0') saw10 = true;
            }
            const bool oscillates = saw01 && saw10;
            printf("  %-52s frames=%s  %s\n", strat.name, seq.c_str(),
                   oscillates ? "<<< МИГАЕТ" : "стабильно");
        }
    }

    // Отдельно: проверяем, что настоящий внешний окклюдер (холм перед секцией) по-прежнему
    // надёжно прячет секцию — независимо от направления смещения бокса.
    printf("\n=== Настоящая окклюзия внешним объектом (холм перед секцией, head_on) ===\n");
    {
        const Box hill{glm::vec3(0, 0, -8), glm::vec3(32, 8, -6)}; // ближе к камере, реальный блокиратор
        const glm::vec3 eye(16, 4, -15), target(16, 4, 0);
        const glm::mat4 view = glm::lookAt(eye, target, glm::vec3(0, 1, 0));
        const glm::mat4 vp = proj * view;
        for (auto& strat : strategies) {
            bool visible = true;
            std::string seq;
            for (int f = 0; f < kFrames; ++f) {
                glViewport(0, 0, 800, 600);
                glClearColor(0, 0, 0, 0);
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
                draw_box_solid(hill, vp); // холм стабильно рисуется каждый кадр всегда
                if (visible) draw_box_solid(section, vp);
                visible = query_box(section, view, proj, strat);
                seq += visible ? '1' : '0';
            }
            printf("  %-52s frames=%s  %s\n", strat.name, seq.c_str(),
                   seq.find('1') == std::string::npos ? "стабильно скрыта (верно)" :
                   "ВИДНА хотя бы иногда — окклюзия холмом не работает!");
        }
    }

    return 0;
}
