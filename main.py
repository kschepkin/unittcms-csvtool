#!/usr/bin/env python3
"""
TMS Tool - Инструмент для импорта/экспорта тест-кейсов
Поддерживает работу с Test Management System через API

Автор: TMS Tool Generator
Версия: 2.0.0
"""

import os
import sys
import json
import csv
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

@dataclass
class TestCaseRow:
    """Структура строки тест-кейса для CSV (одна строка может быть шагом или основной информацией)"""
    id: str = ""
    title: str = ""
    state: str = ""
    priority: str = ""
    type: str = ""
    automation_status: str = ""
    description: str = ""
    pre_conditions: str = ""
    expected_results: str = ""
    template: str = ""
    steps: str = ""
    result: str = ""
    folder_id: str = ""
    folder_name: str = ""
    created_at: str = ""
    updated_at: str = ""

class TMSClient:
    """Клиент для работы с TMS API"""
    
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.password = password
        self.token = None
        self.session = requests.Session()
        
    def authenticate(self) -> bool:
        """Аутентификация в системе"""
        try:
            url = f"{self.base_url}/users/signin"
            data = {
                "email": self.email,
                "password": self.password
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            auth_data = response.json()
            self.token = auth_data.get('access_token')
            
            if self.token:
                self.session.headers.update({
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json'
                })
                logger.info("✓ Успешная аутентификация")
                return True
            else:
                logger.error("✗ Не удалось получить токен")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка аутентификации: {e}")
            return False
    
    def get_projects(self) -> List[Dict]:
        """Получение списка проектов пользователя"""
        try:
            url = f"{self.base_url}/projects?onlyUserProjects=true"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка получения проектов: {e}")
            return []
    
    def get_project_with_cases(self, project_id: int) -> Dict:
        """Получение проекта со всеми тест-кейсами через /home endpoint"""
        try:
            url = f"{self.base_url}/home/{project_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка получения структуры проекта: {e}")
            return {}
    
    def get_folders(self, project_id: int) -> List[Dict]:
        """Получение списка папок в проекте"""
        try:
            url = f"{self.base_url}/folders?projectId={project_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка получения папок: {e}")
            return []
    
    def create_folder(self, project_id: int, name: str, detail: str = "", parent_id: Optional[int] = None) -> Optional[Dict]:
        """Создание новой папки"""
        try:
            url = f"{self.base_url}/folders?projectId={project_id}"
            data = {
                "name": name,
                "detail": detail,
                "parentFolderId": parent_id
            }
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка создания папки: {e}")
            return None
    
    def get_all_cases_detailed(self, project_data: Dict) -> List[Dict]:
        """Получение всех тест-кейсов с полной детализацией"""
        all_cases = []
        
        # Собираем все тест-кейсы из всех папок
        folders = project_data.get('Folders', [])
        
        for folder in folders:
            if 'Cases' in folder:
                for case in folder['Cases']:
                    # Получаем детальную информацию о каждом кейсе
                    detailed_case = self.get_case(case['id'])
                    if detailed_case:
                        # Добавляем информацию о папке
                        detailed_case['folderName'] = folder['name']
                        detailed_case['folderId'] = folder['id']
                        all_cases.append(detailed_case)
                        
        return all_cases
    
    def get_case(self, case_id: int) -> Optional[Dict]:
        """Получение детальной информации о тест-кейсе"""
        try:
            url = f"{self.base_url}/cases/{case_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка получения тест-кейса {case_id}: {e}")
            return None
    
    def create_case(self, folder_id: int, case_data: Dict) -> Optional[Dict]:
        """Создание нового тест-кейса"""
        try:
            url = f"{self.base_url}/cases?folderId={folder_id}"
            response = self.session.post(url, json=case_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка создания тест-кейса: {e}")
            return None
    
    def update_case_steps(self, case_id: int, steps_data: List[Dict]) -> Optional[Dict]:
        """Обновление шагов тест-кейса через отдельный endpoint"""
        try:
            url = f"{self.base_url}/steps/update?caseId={case_id}"
            
            logger.info(f"Отправка POST запроса для обновления {len(steps_data)} шагов кейса {case_id}")
            
            response = self.session.post(url, json=steps_data)
            
            if response.status_code != 200:
                logger.error(f"Ошибка HTTP {response.status_code}: {response.text}")
                return None
            
            result = response.json()
            logger.info(f"Успешно обновлены шаги для кейса {case_id}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Ошибка обновления шагов: {e}")
            return None

class CSVHandler:
    """Обработчик CSV файлов для тест-кейсов в табличном формате"""
    
    # CSV заголовки в правильном порядке
    CSV_HEADERS = [
        'id', 'title', 'state', 'priority', 'type', 'automation_status',
        'description', 'pre_conditions', 'expected_results', 'template',
        'steps', 'result', 'folder_id', 'folder_name', 'created_at', 'updated_at'
    ]
    
    @classmethod
    def export_to_csv(cls, test_cases: List[Dict], file_path: str) -> bool:
        """Экспорт тест-кейсов в CSV файл в табличном формате"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # Записываем заголовок
                writer.writerow(cls.CSV_HEADERS + [''])  # Добавляем пустую колонку в конце
                
                for case in test_cases:
                    # Основная строка с информацией о тест-кейсе
                    main_row = [
                        case.get('id', ''),
                        case.get('title', ''),
                        case.get('state', 0),
                        case.get('priority', 1),
                        case.get('type', 0),
                        case.get('automationStatus', 0),
                        case.get('description', ''),
                        '',  # pre_conditions будет в отдельных строках
                        '',  # expected_results будет в отдельных строках
                        case.get('template', 0),
                        '',  # steps номер шага
                        '',  # result описание шага
                        case.get('folderId', ''),
                        case.get('folderName', ''),
                        case.get('createdAt', ''),
                        case.get('updatedAt', ''),
                        ''  # Пустая колонка в конце
                    ]
                    
                    # Если есть шаги
                    if case.get('Steps') and case.get('template') == 1:
                        # Первая строка с основной информацией и первым шагом
                        steps = case['Steps']
                        if steps:
                            first_step = steps[0]
                            main_row[10] = f"{first_step.get('caseSteps', {}).get('stepNo', 1)}. {first_step.get('step', '')}"
                            main_row[11] = first_step.get('result', '')
                        
                        writer.writerow(main_row)
                        
                        # Остальные шаги в отдельных строках
                        for step in steps[1:]:
                            step_row = [''] * len(cls.CSV_HEADERS) + ['']
                            step_row[10] = f"{step.get('caseSteps', {}).get('stepNo', 1)}. {step.get('step', '')}"
                            step_row[11] = step.get('result', '')
                            writer.writerow(step_row)
                    
                    # Если есть предусловия
                    elif case.get('preConditions'):
                        # Разбиваем предусловия на строки
                        preconditions = case['preConditions'].split('\n')
                        if preconditions:
                            main_row[10] = preconditions[0]
                            main_row[11] = case.get('expectedResults', '')
                            writer.writerow(main_row)
                            
                            # Остальные предусловия в отдельных строках
                            for precondition in preconditions[1:]:
                                if precondition.strip():
                                    precondition_row = [''] * len(cls.CSV_HEADERS) + ['']
                                    precondition_row[10] = precondition.strip()
                                    writer.writerow(precondition_row)
                        else:
                            writer.writerow(main_row)
                    else:
                        # Простой тест-кейс без шагов
                        if case.get('preConditions'):
                            main_row[10] = case['preConditions']
                        main_row[11] = case.get('expectedResults', '')
                        writer.writerow(main_row)
            
            logger.info(f"✓ Экспортировано {len(test_cases)} тест-кейсов в {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Ошибка экспорта в CSV: {e}")
            return False
    
    @classmethod
    def import_from_csv(cls, file_path: str) -> List[Dict]:
        """Импорт тест-кейсов из CSV файла в табличном формате"""
        try:
            test_cases = []
            current_case = None
            
            with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile, delimiter=';')
                headers = next(reader)  # Пропускаем заголовок
                
                for row in reader:
                    if len(row) < len(cls.CSV_HEADERS):
                        # Дополняем строку пустыми значениями
                        row.extend([''] * (len(cls.CSV_HEADERS) - len(row)))
                    
                    # Если есть ID в первой колонке - это начало нового тест-кейса
                    if row[0].strip():  # id не пустой
                        # Сохраняем предыдущий кейс если был
                        if current_case:
                            test_cases.append(current_case)
                        
                        # Создаем новый кейс
                        current_case = {
                            'id': row[0].strip() if row[0].strip() else None,
                            'title': row[1].strip(),
                            'state': int(row[2]) if row[2].strip() else 0,
                            'priority': int(row[3]) if row[3].strip() else 1,
                            'type': int(row[4]) if row[4].strip() else 0,
                            'automationStatus': int(row[5]) if row[5].strip() else 0,
                            'description': row[6].strip(),
                            'template': int(row[9]) if row[9].strip() else 0,
                            'folderId': int(row[12]) if row[12].strip() and row[12].isdigit() else None,
                            'folderName': row[13].strip(),
                            'steps': [],
                            'preConditions': '',
                            'expectedResults': row[11].strip()
                        }
                        
                        # Добавляем первый шаг/предусловие если есть
                        if row[10].strip():
                            if current_case['template'] == 1:  # Пошаговый
                                current_case['steps'].append({
                                    'step': row[10].strip(),
                                    'result': row[11].strip(),
                                    'stepNo': 1
                                })
                            else:  # Простой
                                current_case['preConditions'] = row[10].strip()
                    
                    # Если ID пустой - это продолжение текущего кейса (дополнительный шаг)
                    elif current_case and row[10].strip():
                        if current_case['template'] == 1:  # Пошаговый
                            step_no = len(current_case['steps']) + 1
                            current_case['steps'].append({
                                'step': row[10].strip(),
                                'result': row[11].strip(),
                                'stepNo': step_no
                            })
                        else:  # Простой - добавляем к предусловиям
                            if current_case['preConditions']:
                                current_case['preConditions'] += '\n' + row[10].strip()
                            else:
                                current_case['preConditions'] = row[10].strip()
                
                # Не забываем последний кейс
                if current_case:
                    test_cases.append(current_case)
            
            logger.info(f"✓ Загружено {len(test_cases)} тест-кейсов из {file_path}")
            return test_cases
            
        except Exception as e:
            logger.error(f"✗ Ошибка импорта из CSV: {e}")
            return []

class TMSTool:
    """Основной класс инструмента TMS"""
    
    def __init__(self):
        self.client = None
        self.csv_handler = CSVHandler()
        
    def setup_client(self) -> bool:
        """Настройка клиента TMS"""
        base_url = os.getenv('TMS_BASE_URL')
        email = os.getenv('TMS_EMAIL')
        password = os.getenv('TMS_PASSWORD')
        
        if not all([base_url, email, password]):
            print("❌ Ошибка: Не заданы параметры подключения в .env файле")
            return False
        
        self.client = TMSClient(base_url, email, password)
        return self.client.authenticate()
    
    def show_main_menu(self):
        """Отображение главного меню"""
        print("\n" + "="*60)
        print("🧪 TMS TOOL - Инструмент управления тест-кейсами")
        print("="*60)
        print("1️⃣  Экспорт тест-кейсов в CSV")
        print("2️⃣  Импорт тест-кейсов из CSV")
        print("3️⃣  Просмотр информации о проектах")
        print("0️⃣  Выход")
        print("="*60)
    
    def select_project(self) -> Optional[Dict]:
        """Выбор проекта"""
        projects = self.client.get_projects()
        
        if not projects:
            print("❌ Нет доступных проектов")
            return None
        
        print("\n📁 Доступные проекты:")
        print("-" * 50)
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project['name']} (ID: {project['id']})")
            if project.get('detail'):
                print(f"   Описание: {project['detail']}")
        
        while True:
            try:
                choice = int(input(f"\nВыберите проект (1-{len(projects)}): "))
                if 1 <= choice <= len(projects):
                    selected_project = projects[choice - 1]
                    print(f"✓ Выбран проект: {selected_project['name']}")
                    return selected_project
                else:
                    print("❌ Неверный номер проекта")
            except ValueError:
                print("❌ Введите корректный номер")
    
    def export_test_cases(self):
        """Экспорт тест-кейсов"""
        print("\n🔄 Экспорт тест-кейсов в CSV")
        
        project = self.select_project()
        if not project:
            return
        
        print(f"\n📥 Загрузка тест-кейсов из проекта '{project['name']}'...")
        
        # Получаем полную структуру проекта через /home endpoint
        project_data = self.client.get_project_with_cases(project['id'])
        
        if not project_data:
            print("❌ Не удалось загрузить данные проекта")
            return
        
        # Получаем все тест-кейсы с детализацией
        cases = self.client.get_all_cases_detailed(project_data)
        
        if not cases:
            print("❌ В проекте нет тест-кейсов")
            return
        
        print(f"📋 Найдено {len(cases)} тест-кейсов")
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"testcases_export_{project['name']}_{timestamp}.csv"
        file_path = os.path.join(os.path.expanduser("~/Downloads/tms-tool"), filename)
        
        # Экспортируем в CSV
        if self.csv_handler.export_to_csv(cases, file_path):
            print(f"✅ Экспорт завершен успешно!")
            print(f"📄 Файл сохранен: {file_path}")
        else:
            print("❌ Ошибка при экспорте")
    
    def import_test_cases(self):
        """Импорт тест-кейсов"""
        print("\n🔄 Импорт тест-кейсов из CSV")
        
        project = self.select_project()
        if not project:
            return
        
        # Запрашиваем путь к файлу
        file_path = input("\n📁 Введите путь к CSV файлу: ").strip()
        
        if not os.path.exists(file_path):
            print("❌ Файл не найден")
            return
        
        # Загружаем тест-кейсы из CSV
        test_cases = self.csv_handler.import_from_csv(file_path)
        if not test_cases:
            return
        
        # Выбираем папку для импорта
        target_folder = self.select_or_create_folder(project['id'])
        if not target_folder:
            return
        
        # Импортируем тест-кейсы
        print(f"\n📤 Импорт {len(test_cases)} тест-кейсов в папку '{target_folder['name']}'...")
        
        success_count = 0
        error_count = 0
        
        for i, test_case in enumerate(test_cases, 1):
            # Подготавливаем основные данные для создания
            case_data = {
                'title': test_case['title'],
                'state': test_case['state'],
                'priority': test_case['priority'],
                'type': test_case['type'],
                'automationStatus': test_case['automationStatus'],
                'description': test_case['description'],
                'template': test_case['template'],
                'preConditions': test_case['preConditions'],
                'expectedResults': test_case['expectedResults']
            }
            
            # Сначала создаем тест-кейс без шагов
            created_case = self.client.create_case(target_folder['id'], case_data)
            
            if not created_case:
                print(f"  ❌ {i}/{len(test_cases)}: Ошибка создания {test_case['title']}")
                error_count += 1
                continue
            
            # Если есть шаги и это пошаговый тест, обновляем его
            if test_case['steps'] and test_case['template'] == 1:
                # Подготавливаем шаги в формате для steps/update endpoint
                api_steps = []
                for j, step in enumerate(test_case['steps']):
                    api_steps.append({
                        'id': 0,  # Для новых шагов всегда 0
                        'step': step['step'],
                        'result': step['result'],
                        'uid': f"uid{j}",  # Уникальный ID для каждого шага
                        'editState': 'new',  # Обязательно для новых шагов
                        'caseSteps': {
                            'stepNo': step['stepNo']
                        }
                    })
                
                # Отладка: выводим информацию о шагах
                logger.info(f"Обновление кейса {created_case['id']} с {len(api_steps)} шагами")
                
                # Обновляем шаги через отдельный endpoint
                updated_steps = self.client.update_case_steps(created_case['id'], api_steps)
                
                if updated_steps:
                    print(f"  ✓ {i}/{len(test_cases)}: {test_case['title']} (с {len(api_steps)} шагами)")
                    success_count += 1
                else:
                    print(f"  ⚠️ {i}/{len(test_cases)}: {test_case['title']} (создан, но шаги не добавлены)")
                    success_count += 1  # Кейс все равно создан
            else:
                # Простой тест-кейс без шагов
                print(f"  ✓ {i}/{len(test_cases)}: {test_case['title']}")
                success_count += 1
        
        print(f"\n✅ Импорт завершен!")
        print(f"✓ Успешно: {success_count}")
        if error_count > 0:
            print(f"❌ Ошибок: {error_count}")
    
    def select_or_create_folder(self, project_id: int) -> Optional[Dict]:
        """Выбор существующей папки или создание новой"""
        folders = self.client.get_folders(project_id)
        
        print("\n📁 Выберите папку для импорта:")
        print("-" * 50)
        print("0. Создать новую папку")
        
        for i, folder in enumerate(folders, 1):
            print(f"{i}. {folder['name']} (ID: {folder['id']})")
            if folder.get('detail'):
                print(f"   Описание: {folder['detail']}")
        
        while True:
            try:
                choice = int(input(f"\nВыберите папку (0-{len(folders)}): "))
                
                if choice == 0:
                    # Создаем новую папку
                    folder_name = input("Введите название новой папки: ").strip()
                    if not folder_name:
                        print("❌ Название папки не может быть пустым")
                        continue
                    
                    folder_detail = input("Введите описание папки (необязательно): ").strip()
                    
                    new_folder = self.client.create_folder(project_id, folder_name, folder_detail)
                    if new_folder:
                        print(f"✓ Создана новая папка: {folder_name}")
                        return new_folder
                    else:
                        print("❌ Ошибка создания папки")
                        return None
                
                elif 1 <= choice <= len(folders):
                    selected_folder = folders[choice - 1]
                    print(f"✓ Выбрана папка: {selected_folder['name']}")
                    return selected_folder
                else:
                    print("❌ Неверный номер папки")
                    
            except ValueError:
                print("❌ Введите корректный номер")
    
    def show_project_info(self):
        """Отображение информации о проектах"""
        print("\n📊 Информация о проектах")
        
        projects = self.client.get_projects()
        if not projects:
            print("❌ Нет доступных проектов")
            return
        
        for project in projects:
            print(f"\n{'='*60}")
            print(f"📁 Проект: {project['name']} (ID: {project['id']})")
            if project.get('detail'):
                print(f"📝 Описание: {project['detail']}")
            print(f"🌐 Публичный: {'Да' if project.get('isPublic') else 'Нет'}")
            print(f"📅 Создан: {project.get('createdAt', 'Н/Д')}")
            
            # Получаем структуру проекта
            project_data = self.client.get_project_with_cases(project['id'])
            folders = project_data.get('Folders', [])
            
            total_cases = 0
            for folder in folders:
                total_cases += len(folder.get('Cases', []))
            
            print(f"📋 Тест-кейсов: {total_cases}")
            print(f"📁 Папок: {len(folders)}")
            
            if folders:
                print("\n📂 Структура папок:")
                for folder in folders:
                    cases_count = len(folder.get('Cases', []))
                    print(f"  • {folder['name']} (ID: {folder['id']}) - {cases_count} кейсов")
    
    def run(self):
        """Запуск приложения"""
        print("🚀 Запуск TMS Tool...")
        
        if not self.setup_client():
            print("❌ Не удалось подключиться к TMS")
            return
        
        while True:
            self.show_main_menu()
            
            try:
                choice = input("\nВыберите действие: ").strip()
                
                if choice == "1":
                    self.export_test_cases()
                elif choice == "2":
                    self.import_test_cases()
                elif choice == "3":
                    self.show_project_info()
                elif choice == "0":
                    print("👋 До свидания!")
                    break
                else:
                    print("❌ Неверный выбор")
                    
                input("\n⏸️  Нажмите Enter для продолжения...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Программа прервана пользователем")
                break
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
                print(f"❌ Произошла ошибка: {e}")

def main():
    """Точка входа в приложение"""
    tool = TMSTool()
    tool.run()

if __name__ == "__main__":
    main()
