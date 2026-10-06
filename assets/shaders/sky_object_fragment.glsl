#version 330 core
in vec2 vLocalPos;
out vec4 FragColor;

uniform vec3 color;
uniform float alpha; // общая непрозрачность диска (для мягкого исчезновения под горизонтом)

void main() {
    const float softness = 0.08;
    float dist = length(vLocalPos);
    float edge = 1.0 - smoothstep(1.0 - softness, 1.0, dist);
    if (edge <= 0.0 || alpha <= 0.0) {
        discard;
    }
    FragColor = vec4(color, edge * alpha);
}
