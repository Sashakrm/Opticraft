#version 330 core
out vec4 FragColor;

in vec2 TexCoord;
in vec3 Normal;
in vec3 FragPos;

uniform sampler2D albedo_texture;
// День/ночь — так же, как у блоков (см. fragment.glsl), чтобы мобы не
// выбивались освещением из общей сцены.
uniform float ambient;
// Красная вспышка при получении урона (0 — нет, 1 — максимум). Ставится в Mob::render.
uniform float hurt_flash;

void main() {
    vec3 normal = normalize(Normal);

    // Простой направленный свет "сверху" + ambient — временная заглушка,
    // пока нет полноценного освещения мобов от солнца/факелов.
    vec3 light_dir = normalize(vec3(0.3, 1.0, 0.4));
    float diffuse = max(dot(normal, light_dir), 0.0);
    float light_intensity = clamp(0.35 + diffuse * 0.65, 0.0, 1.0) * max(ambient, 0.4);

    vec4 tex_color = texture(albedo_texture, TexCoord);
    if (tex_color.a < 0.1) discard; // альфа-каттинг для текстур с прозрачностью

    vec3 lit_color = tex_color.rgb * light_intensity;
    lit_color = mix(lit_color, vec3(1.0, 0.15, 0.15), clamp(hurt_flash, 0.0, 1.0) * 0.55);

    FragColor = vec4(lit_color, tex_color.a);
}
