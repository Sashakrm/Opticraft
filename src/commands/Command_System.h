//
// Система чат-команд в стиле Minecraft: "/tp ~ ~10 ~", "/time set night", "/give ..." и т.д.
//
// Парсер не лезет во внутренности движка: всё, что команды умеют делать, — это публичные
// методы Game (teleport_player, locate_biome, give_item, ...). Поэтому новая команда =
// одна ветка в execute_command + (если нужно) один публичный метод в Game.
//
#ifndef OPTICRAFT_COMMAND_SYSTEM_H
#define OPTICRAFT_COMMAND_SYSTEM_H

#include <string>
#include <vector>

class Game;

// Исполняет строку БЕЗ ведущего '/'. Текст ответа (может быть многострочным, '\n')
// кладёт в reply. Возвращает true, если команда выполнена успешно (false — ошибка
// синтаксиса/аргументов; ответ тогда рисуется в чате красным).
bool execute_command(Game& game, const std::string& input, std::string& reply);

// Варианты для Tab-дополнения. input — вся строка ввода (с ведущим '/', если он есть).
// Возвращает полные варианты ЦЕЛЫХ строк ввода (команда + уже введённые аргументы + вариант).
std::vector<std::string> get_command_completions(const std::string& input);

#endif // OPTICRAFT_COMMAND_SYSTEM_H
