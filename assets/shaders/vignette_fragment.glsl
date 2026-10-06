#version 330 core
in vec2 vUV;
out vec4 FragColor;

// Соответствует legacy Vignette.png (радиальный градиент), но считается процедурно,
// чтобы не тащить в движок отдельный текстурный конвейер только ради одного эффекта.
uniform float aspect;
uniform float radius;
uniform float softness;
uniform float strength;

void main() {
    vec2 centered = (vUV - vec2(0.5)) * vec2(aspect, 1.0);
    float dist = length(centered);
    float vignette_amount = smoothstep(radius, radius + softness, dist);
    FragColor = vec4(0.0, 0.0, 0.0, vignette_amount * strength);
}
