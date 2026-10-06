#version 330 core
// Выпавшие предметы: тот же атлас и то же освещение, что у блоков (см. fragment.glsl),
// плюс отсечение прозрачных пикселей — плоские спрайты (мясо, уголь) не имеют сплошного фона.
out vec4 FragColor;

in vec2 TexCoord;
in vec3 Normal;
in vec3 FragPos;
in float BlockLight;

uniform sampler2D textureAtlas;
uniform float ambient;
uniform float maxLightLevel;

void main() {
    vec4 tex_color = texture(textureAtlas, TexCoord);
    if (tex_color.a < 0.1) discard;

    float light_intensity = 0.8;
    if (Normal.y > 0.9) light_intensity = 1.0;
    else if (Normal.y < -0.9) light_intensity = 0.55;

    float packed_light = floor(BlockLight + 0.5);
    float block_light = mod(packed_light, 16.0);
    float sky_light = floor(packed_light / 16.0);
    float scene_light = max(max((sky_light / 15.0) * ambient, block_light / maxLightLevel), 0.34);

    FragColor = vec4(tex_color.rgb * light_intensity * scene_light, tex_color.a);
}
