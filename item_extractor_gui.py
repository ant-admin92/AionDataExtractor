import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, 
                           QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                           QFileDialog, QProgressBar, QLabel, QListWidget, QComboBox, 
                           QLineEdit, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
import xml.etree.ElementTree as ET
import shutil

class DataExtractorWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, xml_files, icon_dir):
        super().__init__()
        self.xml_files = xml_files
        
        # 파일 분류 저장
        self.string_files = []
        self.item_files = []
        self.other_files = []
        
        # 기본 데이터 저장소
        self.strings = {}
        self.string_sources = {}  # 각 스트링이 어떤 파일에서 왔는지 저장
        self.name_id_map = {}  # 이름과 ID 매핑
        
        # 카테고리별 데이터 저장소
        self.data_categories = {
            'items': {},      # 아이템
            'npcs': {},       # NPC
            'pets': {},       # 펫
            'mounts': {},     # 탑승물
            'wings': {},      # 날개
            'quests': {},     # 퀘스트
            'skills': {},     # 스킬
            'titles': {},     # 칭호
            'housing': {},    # 하우징
            'other': {}       # 기타
        }
        
        # 아이템 상세 분류
        self.item_subcategories = {
            'equipment': {    # 장비
                'armor': [],      # 방어구
                'weapon': [],     # 무기
                'accessory': [],  # 장신구
                'wing': [],       # 날개
            },
            'consumable': {   # 소비
                'potion': [],     # 포션
                'scroll': [],     # 주문서
                'food': [],       # 음식
            },
            'material': {     # 재료
                'craft': [],      # 제작
                'enchant': [],    # 인챈트
                'quest': [],      # 퀘스트
            },
            'other': {        # 기타
                'quest': [],      # 퀘스트
                'event': [],      # 이벤트
                'misc': [],       # 기타
            }
        }

    def classify_xml_files(self):
        """선택된 XML 파일 분류"""
        self.string_files.clear()
        self.item_files.clear()
        self.other_files.clear()
        
        self.progress.emit("파일 분류 중...")
        
        for file in self.xml_files:
            try:
                parser = ET.XMLParser(encoding="utf-8")
                tree = ET.parse(file, parser=parser)
                root = tree.getroot()
                
                # 파일 타입 확인
                if root.find(".//string") is not None:
                    self.string_files.append(file)
                    self.progress.emit(f"스트링 파일 발견: {os.path.basename(file)}")
                elif root.find(".//client_item") is not None:
                    self.item_files.append(file)
                    self.progress.emit(f"아이템 파일 발견: {os.path.basename(file)}")
                else:
                    self.other_files.append(file)
                    self.progress.emit(f"기타 파일 발견: {os.path.basename(file)}")
                    
            except Exception as e:
                self.progress.emit(f"파일 분류 중 오류 ({os.path.basename(file)}): {str(e)}")
        
        # 분류 완료 메시지
        self.progress.emit(f"\n파일 분류 완료:")
        self.progress.emit(f"- 스트링 파일: {len(self.string_files)}개")
        self.progress.emit(f"- 아이템 파일: {len(self.item_files)}개")
        self.progress.emit(f"- 기타 파일: {len(self.other_files)}개")

    def process_strings(self, root, file_name):
        """스트링 데이터 처리"""
        string_count = 0
        
        for string in root.findall(".//string"):
            try:
                id_elem = string.find("id")
                name_elem = string.find("name")
                body_elem = string.find("body")
                
                if id_elem is not None and name_elem is not None and body_elem is not None:
                    string_id = id_elem.text
                    name_text = name_elem.text
                    body_text = body_elem.text
                    
                    # 스트링 데이터 저장
                    self.strings[name_text] = body_text
                    # 스트링 소스 파일 저장
                    self.string_sources[name_text] = file_name
                    string_count += 1
                        
            except Exception as e:
                continue
                
        self.progress.emit(f"스트링 처리: {string_count}개")

    def process_item_data(self, root, file_name):
        """아이템 데이터 처리"""
        processed_count = 0
        error_count = 0
        name_not_found = 0
        
        # 스트링 파일 찾기
        string_file = "Unknown"
        for file in self.string_files:
            if os.path.basename(file).startswith("string_"):
                string_file = os.path.basename(file)
                break
        
        for item in root.findall(".//client_item"):
            try:
                id_elem = item.find("id")
                if id_elem is None:
                    continue
                    
                item_id = id_elem.text
                item_info = self.extract_item_info(item, file_name)
                
                if item_info is not None:
                    # 아이템 기본 정보 저장
                    self.data_categories['items'][item_id] = item_info
                    
                    # 아이템 서브카테고리 분류
                    self.categorize_item(item_info)
                    
                    processed_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                continue

        # 최종 처리 결과 보고
        self.progress.emit(f"아이템 처리: {processed_count}개 (실패: {error_count}개)")

    def extract_item_info(self, item, file_name):
        """아이템 정보 추출"""
        try:
            item_id = item.find("id").text if item.find("id") is not None else "Unknown"
            name_elem = item.find("name")
            desc_elem = item.find("desc")
            
            # 이름과 설명 가져오기
            name_code = name_elem.text if name_elem is not None else "Unknown"
            desc_code = desc_elem.text if desc_elem is not None else "Unknown"
            
            # 스트링에서 실제 텍스트 찾기
            item_name = self.strings.get(name_code, name_code)
            item_desc = self.strings.get(desc_code, desc_code)
            
            # 스트링 파일 찾기
            string_file = self.string_sources.get(name_code, "Unknown")
            if string_file == "Unknown" and desc_code in self.string_sources:
                string_file = self.string_sources[desc_code]
            
            return {
                'id': item_id,
                'name_code': name_code,
                'name': item_name,
                'desc_code': desc_code,
                'desc': item_desc,
                'icon': item.find("icon_name").text if item.find("icon_name") is not None else "Unknown",
                'type': item.find("item_type").text if item.find("item_type") is not None else "Unknown",
                'quality': item.find("quality").text if item.find("quality") is not None else "Unknown",
                'level': item.find("level").text if item.find("level") is not None else "Unknown",
                'equipment_slots': item.find("equipment_slots").text if item.find("equipment_slots") is not None else "Unknown",
                'category': item.find("category").text if item.find("category") is not None else "Unknown",
                'item_file': file_name,
                'string_file': string_file
            }
        except Exception:
            return None

    def categorize_item(self, item_info):
        """아이템 서브카테고리 분류"""
        item_type = item_info['type'].lower()
        category = item_info['category'].lower()
        
        if 'armor' in item_type or 'shield' in item_type:
            self.item_subcategories['equipment']['armor'].append(item_info)
        elif 'weapon' in item_type:
            self.item_subcategories['equipment']['weapon'].append(item_info)
        elif 'accessory' in item_type:
            self.item_subcategories['equipment']['accessory'].append(item_info)
        elif 'wing' in item_type:
            self.item_subcategories['equipment']['wing'].append(item_info)
        elif 'potion' in item_type:
            self.item_subcategories['consumable']['potion'].append(item_info)
        elif 'scroll' in item_type:
            self.item_subcategories['consumable']['scroll'].append(item_info)
        elif 'food' in item_type:
            self.item_subcategories['consumable']['food'].append(item_info)
        elif 'material' in item_type:
            if 'craft' in category:
                self.item_subcategories['material']['craft'].append(item_info)
            elif 'enchant' in category:
                self.item_subcategories['material']['enchant'].append(item_info)
            elif 'quest' in category:
                self.item_subcategories['material']['quest'].append(item_info)
        elif 'quest' in category:
            self.item_subcategories['other']['quest'].append(item_info)
        elif 'event' in category:
            self.item_subcategories['other']['event'].append(item_info)
        else:
            self.item_subcategories['other']['misc'].append(item_info)

    def process_npc_data(self, root, file_name):
        """NPC 데이터 처리"""
        for npc in root.findall(".//client_npc"):
            try:
                id_elem = npc.find("id")
                if id_elem is None:
                    continue
                    
                npc_id = id_elem.text
                self.data_categories['npcs'][npc_id] = {
                    'id': npc_id,
                    'name': npc.find("name").text if npc.find("name") is not None else "Unknown",
                    'title': npc.find("title").text if npc.find("title") is not None else "Unknown",
                    'desc': npc.find("desc").text if npc.find("desc") is not None else "Unknown",
                    'desc_text': self.strings.get(npc.find("desc").text if npc.find("desc") is not None else "", "Unknown"),
                    'icon': npc.find("icon_name").text if npc.find("icon_name") is not None else "Unknown",
                    'type': npc.find("npc_type").text if npc.find("npc_type") is not None else "Unknown",
                    'file': file_name
                }
            except Exception as e:
                self.progress.emit(f"NPC 처리 중 오류 (ID: {npc_id}): {str(e)}")

    def process_quest_data(self, root, file_name):
        """퀘스트 데이터 처리"""
        for quest in root.findall(".//quest"):
            try:
                id_elem = quest.get("id")
                if id_elem is None:
                    continue
                    
                quest_id = id_elem
                self.data_categories['quests'][quest_id] = {
                    'id': quest_id,
                    'name': quest.find("name").text if quest.find("name") is not None else "Unknown",
                    'desc': quest.find("desc").text if quest.find("desc") is not None else "Unknown",
                    'desc_text': self.strings.get(quest.find("desc").text if quest.find("desc") is not None else "", "Unknown"),
                    'category': quest.find("category").text if quest.find("category") is not None else "Unknown",
                    'level': quest.find("level").text if quest.find("level") is not None else "Unknown",
                    'file': file_name
                }
            except Exception as e:
                self.progress.emit(f"퀘스트 처리 중 오류 (ID: {quest_id}): {str(e)}")

    def parse_xml_file(self, file_path):
        """XML 파일 파싱 및 분류"""
        try:
            self.progress.emit(f"파일 처리 중: {os.path.basename(file_path)}")
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(file_path, parser=parser)
            root = tree.getroot()
            file_name = os.path.basename(file_path)
            
            # 파일 타입 자동 감지 및 처리
            if root.find(".//string") is not None:
                self.process_strings(root, file_name)
            elif root.find(".//client_item") is not None:
                self.process_item_data(root, file_name)
            elif root.find(".//client_npc") is not None:
                self.process_npc_data(root, file_name)
            elif root.find(".//quest") is not None:
                self.process_quest_data(root, file_name)
            # 추가 타입들은 여기에 구현...
            
        except ET.ParseError as e:
            self.progress.emit(f"XML 파싱 오류 ({os.path.basename(file_path)}): {str(e)}")
            self.progress.emit("해당 파일을 건너뜁니다.")
        except Exception as e:
            self.progress.emit(f"파일 처리 중 오류 발생 ({os.path.basename(file_path)}): {str(e)}")

    def run(self):
        """메인 실행 함수"""
        try:
            # XML 파일 분류
            self.classify_xml_files()
            
            if not self.string_files:
                self.progress.emit("경고: 스트링 파일이 없습니다!")
                return
                
            if not self.item_files:
                self.progress.emit("경고: 아이템 파일이 없습니다!")
                return
            
            # 먼저 스트링 파일 처리
            self.progress.emit("\n스트링 파일 처리 중...")
            for file in self.string_files:
                try:
                    parser = ET.XMLParser(encoding="utf-8")
                    tree = ET.parse(file, parser=parser)
                    root = tree.getroot()
                    self.process_strings(root, os.path.basename(file))
                except Exception:
                    continue

            # 아이템 파일 처리
            self.progress.emit("\n아이템 파일 처리 중...")
            for file in self.item_files:
                try:
                    parser = ET.XMLParser(encoding="utf-8")
                    tree = ET.parse(file, parser=parser)
                    root = tree.getroot()
                    self.process_item_data(root, os.path.basename(file))
                except Exception:
                    continue
            
            # 기타 파일 처리
            if self.other_files:
                self.progress.emit("\n기타 파일 처리 중...")
                for file in self.other_files:
                    try:
                        self.parse_xml_file(file)
                    except Exception:
                        continue
            
            # 결과 데이터 생성
            result_data = {
                'categories': self.data_categories,
                'item_subcategories': self.item_subcategories,
                'strings': self.strings,
                'name_id_map': self.name_id_map
            }
            
            self.finished.emit(result_data)
            
        except Exception as e:
            self.progress.emit(f"처리 중 오류 발생: {str(e)}")

    def save_category_data(self, category, data, save_dir):
        """카테고리별 데이터 저장"""
        save_path = os.path.join(save_dir, f'{category}_info.txt')
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(f"=== {category.upper()} 정보 ===\n\n")
            f.write(f"총 {len(data)}개 항목\n")
            f.write("-" * 50 + "\n\n")
            
            for item_id, item_info in data.items():
                f.write(f"ID: {item_id}\n")
                if 'name_code' in item_info:
                    f.write(f"이름 코드: {item_info['name_code']}\n")
                    f.write(f"이름: {item_info['name']}\n")
                if 'desc_code' in item_info:
                    f.write(f"설명 코드: {item_info['desc_code']}\n")
                    f.write(f"설명: {item_info['desc']}\n")
                for key, value in item_info.items():
                    if key not in ['id', 'name_code', 'desc_code', 'name', 'desc']:
                        f.write(f"{key}: {value}\n")
                f.write("-" * 30 + "\n")

    def save_item_subcategories(self, subcategories, save_dir):
        """아이템 서브카테고리 데이터 저장"""
        save_path = os.path.join(save_dir, 'item_subcategories.txt')
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write("=== 아이템 상세 분류 ===\n\n")
            
            for main_cat, sub_cats in subcategories.items():
                f.write(f"\n=== {main_cat} ===\n")
                for sub_cat, items in sub_cats.items():
                    if items:
                        f.write(f"\n--- {sub_cat} ({len(items)}개) ---\n")
                        for item in items:
                            f.write(f"\nID: {item['id']}\n")
                            if 'name_code' in item:
                                f.write(f"이름 코드: {item['name_code']}\n")
                                f.write(f"이름: {item['name']}\n")
                            if 'desc_code' in item:
                                f.write(f"설명 코드: {item['desc_code']}\n")
                                f.write(f"설명: {item['desc']}\n")
                            f.write("-" * 20 + "\n")

class ItemIconWidget(QWidget):
    def __init__(self, icon_path=None):
        super().__init__()
        layout = QVBoxLayout(self)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        layout.addWidget(self.icon_label)
        if icon_path:
            self.set_icon(icon_path)

    def set_icon(self, icon_path):
        try:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.icon_label.setPixmap(scaled_pixmap)
            else:
                self.icon_label.setText("No Icon")
        except Exception:
            self.icon_label.setText("Error")

class ItemExtractorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("아이온 데이터 추출기")
        self.setGeometry(100, 100, 600, 800)
        self.setFixedSize(600, 800)  # 창 크기 고정
        
        # 메인 위젯 설정
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 탭 위젯 생성
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # XML 파일 탭
        xml_tab = QWidget()
        xml_layout = QVBoxLayout(xml_tab)
        
        # XML 파일 선택 버튼과 초기화 버튼을 위한 수평 레이아웃
        button_layout = QHBoxLayout()
        
        # XML 파일 선택 버튼
        xml_btn = QPushButton("XML 파일 선택")
        xml_btn.clicked.connect(self.select_xml_files)
        button_layout.addWidget(xml_btn)
        
        # 초기화 버튼
        reset_btn = QPushButton("초기화")
        reset_btn.clicked.connect(self.reset_all)
        button_layout.addWidget(reset_btn)
        
        xml_layout.addLayout(button_layout)
        
        # 파일 리스트를 표시할 위젯들
        lists_layout = QHBoxLayout()
        
        # 스트링 파일 리스트
        string_group = QWidget()
        string_layout = QVBoxLayout(string_group)
        string_layout.addWidget(QLabel("스트링 파일"))
        self.string_list = QListWidget()
        string_layout.addWidget(self.string_list)
        lists_layout.addWidget(string_group)
        
        # 아이템 파일 리스트
        item_group = QWidget()
        item_layout = QVBoxLayout(item_group)
        item_layout.addWidget(QLabel("아이템 파일"))
        self.item_list = QListWidget()
        item_layout.addWidget(self.item_list)
        lists_layout.addWidget(item_group)
        
        # 기타 파일 리스트
        other_group = QWidget()
        other_layout = QVBoxLayout(other_group)
        other_layout.addWidget(QLabel("기타 파일"))
        self.other_list = QListWidget()
        other_layout.addWidget(self.other_list)
        lists_layout.addWidget(other_group)
        
        xml_layout.addLayout(lists_layout)
        tabs.addTab(xml_tab, "XML 파일")
        
        # 검색 탭 추가
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        
        # 검색 옵션
        search_option_layout = QHBoxLayout()
        self.search_type = QComboBox()
        self.search_type.addItems([
            "아이템 ID", "아이템 이름", "NPC", "퀘스트", 
            "펫", "탑승물", "날개", "스킬", "기타"
        ])
        search_option_layout.addWidget(self.search_type)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요...")
        search_option_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("검색")
        search_btn.clicked.connect(self.search_data)
        search_option_layout.addWidget(search_btn)
        
        search_layout.addLayout(search_option_layout)
        
        # 검색 결과 표시
        self.search_result = QTextEdit()
        self.search_result.setReadOnly(True)
        search_layout.addWidget(self.search_result)
        
        tabs.addTab(search_tab, "검색")
        
        # 진행상황 표시
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        layout.addWidget(self.progress_text)
        
        # 진행바 레이아웃
        progress_layout = QHBoxLayout()
        
        # 파일 분류 진행바
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        progress_layout.addWidget(QLabel("분류"))
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)
        
        # 추출 진행바
        extract_layout = QHBoxLayout()
        self.extract_progress_bar = QProgressBar()
        self.extract_progress_bar.setFixedHeight(20)
        extract_layout.addWidget(QLabel("추출"))
        extract_layout.addWidget(self.extract_progress_bar)
        layout.addLayout(extract_layout)
        
        # 실행 버튼
        process_btn = QPushButton("추출 시작")
        process_btn.clicked.connect(self.start_processing)
        layout.addWidget(process_btn)
        
        # 파일 리스트 저장
        self.xml_files = []

    def select_xml_files(self):
        """XML 파일 선택"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "XML 파일 선택", "", "XML Files (*.xml)")
        if files:
            self.xml_files = files
            self.classify_xml_files()

    def classify_xml_files(self):
        """선택된 XML 파일 분류"""
        self.string_list.clear()
        self.item_list.clear()
        self.other_list.clear()
        
        # 진행 상태 표시 초기화
        total_files = len(self.xml_files)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        self.progress_text.append("파일 분류 중...")
        
        for index, file in enumerate(self.xml_files, 1):
            try:
                parser = ET.XMLParser(encoding="utf-8")
                tree = ET.parse(file, parser=parser)
                root = tree.getroot()
                
                # 파일 타입 확인
                if root.find(".//string") is not None:
                    self.string_list.addItem(os.path.basename(file))
                elif root.find(".//client_item") is not None:
                    self.item_list.addItem(os.path.basename(file))
                else:
                    self.other_list.addItem(os.path.basename(file))
                
                # 진행 상태 업데이트
                self.progress_bar.setValue(index)
                QApplication.processEvents()  # UI 업데이트
                    
            except Exception as e:
                self.progress_text.append(f"파일 분류 중 오류 ({os.path.basename(file)}): {str(e)}")
        
        # 분류 완료 메시지
        self.progress_text.append(f"\n파일 분류 완료:")
        self.progress_text.append(f"- 스트링 파일: {self.string_list.count()}개")
        self.progress_text.append(f"- 아이템 파일: {self.item_list.count()}개")
        self.progress_text.append(f"- 기타 파일: {self.other_list.count()}개")

    def search_data(self):
        """데이터 검색"""
        search_text = self.search_input.text().strip().lower()
        search_type = self.search_type.currentText()
        
        if not hasattr(self, 'worker'):
            self.search_result.setText("먼저 데이터를 로드해주세요.")
            return
            
        results = []
        
        # 검색 타입에 따른 처리
        if search_type == "아이템 ID":
            results = self.search_by_id(search_text, 'items')
        elif search_type == "아이템 이름":
            results = self.search_by_name(search_text, 'items')
        elif search_type == "NPC":
            results = self.search_by_name(search_text, 'npcs')
        elif search_type == "퀘스트":
            results = self.search_by_name(search_text, 'quests')
        elif search_type == "펫":
            results = self.search_by_name(search_text, 'pets')
        elif search_type == "탑승물":
            results = self.search_by_name(search_text, 'mounts')
        elif search_type == "날개":
            results = self.search_by_name(search_text, 'wings')
        elif search_type == "스킬":
            results = self.search_by_name(search_text, 'skills')
        else:
            results = self.search_by_name(search_text, 'other')
            
        self.display_search_results(results, search_type)

    def search_by_id(self, search_text, category):
        """ID로 검색"""
        results = []
        category_data = self.worker.data_categories.get(category, {})
        
        for item_id, item_info in category_data.items():
            if search_text in str(item_id).lower():
                results.append(item_info)
                
        return results

    def search_by_name(self, search_text, category):
        """이름으로 검색"""
        results = []
        category_data = self.worker.data_categories.get(category, {})
        
        for item_info in category_data.values():
            # 이름과 설명에서 검색
            name = item_info.get('name', '')
            desc = item_info.get('desc', '')
            
            # 한글 이름이 있는 경우 한글 이름으로 검색
            if isinstance(name, str) and search_text in name.lower():
                results.append(item_info)
            elif isinstance(desc, str) and search_text in desc.lower():
                results.append(item_info)
                
        return results

    def display_search_results(self, results, search_type):
        """검색 결과 표시"""
        if not results:
            self.search_result.setText("검색 결과가 없습니다.")
            return
            
        self.search_result.clear()
        self.search_result.append(f"검색 결과: {len(results)}개 항목 발견\n")
        self.search_result.append("-" * 40 + "\n")
        
        for item in results:
            self.search_result.append(f"ID: {item['id']}")
            
            # 이름 표시 (한글 이름이 있는 경우)
            if 'name' in item and item['name']:
                self.search_result.append(f"이름: {item['name']}")
            
            # 설명 표시 (한글 설명이 있는 경우)
            if 'desc' in item and item['desc']:
                self.search_result.append(f"설명: {item['desc']}")
            
            # 기타 정보 표시
            if 'type' in item:
                self.search_result.append(f"타입: {item['type']}")
            if 'category' in item:
                self.search_result.append(f"카테고리: {item['category']}")
            if 'level' in item:
                self.search_result.append(f"레벨: {item['level']}")
            if 'item_file' in item:
                self.search_result.append(f"아이템 파일: {item['item_file']}")
            if 'string_file' in item:
                self.search_result.append(f"스트링 파일: {item['string_file']}")
            self.search_result.append("-" * 40 + "\n")

    def start_processing(self):
        """데이터 처리 시작"""
        if not self.xml_files:
            self.progress_text.append("오류: XML 파일을 선택해주세요.")
            return
            
        if self.string_list.count() == 0:
            self.progress_text.append("오류: 스트링 파일이 없습니다.")
            return
            
        if self.item_list.count() == 0:
            self.progress_text.append("오류: 아이템 파일이 없습니다.")
            return

        self.progress_text.clear()
        self.progress_text.append("처리 시작...")
        
        # 추출 진행바 초기화
        self.extract_progress_bar.setMaximum(100)
        self.extract_progress_bar.setValue(0)
        
        # XML 파일이 있는 디렉토리 경로
        base_dir = os.path.dirname(self.xml_files[0])
        
        # 분류된 파일 목록 생성
        string_files = [os.path.join(base_dir, self.string_list.item(i).text()) 
                       for i in range(self.string_list.count())]
        item_files = [os.path.join(base_dir, self.item_list.item(i).text()) 
                     for i in range(self.item_list.count())]
        other_files = [os.path.join(base_dir, self.other_list.item(i).text()) 
                      for i in range(self.other_list.count())]
        
        self.worker = DataExtractorWorker(
            self.xml_files,
            ""
        )
        self.worker.string_files = string_files
        self.worker.item_files = item_files
        self.worker.other_files = other_files
        
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_complete)
        self.worker.start()

    def update_progress(self, message):
        """진행상황 업데이트"""
        self.progress_text.append(message)
        
        # 추출 진행바 업데이트
        if "스트링 처리:" in message:
            try:
                count = int(message.split(":")[1].split("개")[0].strip())
                self.extract_progress_bar.setValue(min(count // 100, 100))
            except:
                pass
        elif "아이템 처리:" in message:
            try:
                count = int(message.split(":")[1].split("개")[0].strip())
                self.extract_progress_bar.setValue(min(50 + count // 100, 100))
            except:
                pass
        elif "처리가 완료되었습니다!" in message:
            self.extract_progress_bar.setValue(100)

    def process_complete(self, results):
        """처리 완료"""
        try:
            # 결과 저장 디렉토리 생성
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            # 카테고리별 결과 저장
            for category, data in results['categories'].items():
                if data:  # 데이터가 있는 경우만 저장
                    try:
                        save_path = os.path.join(save_dir, f'{category}_info.txt')
                        with open(save_path, 'w', encoding='utf-8') as f:
                            f.write(f"=== {category.upper()} 정보 ===\n\n")
                            f.write(f"총 {len(data)}개 항목\n")
                            f.write("-" * 50 + "\n\n")
                            
                            for item_id, item_info in data.items():
                                f.write(f"ID: {item_id}\n")
                                if 'name_code' in item_info:
                                    f.write(f"이름 코드: {item_info['name_code']}\n")
                                    f.write(f"이름: {item_info['name']}\n")
                                if 'desc_code' in item_info:
                                    f.write(f"설명 코드: {item_info['desc_code']}\n")
                                    f.write(f"설명: {item_info['desc']}\n")
                                for key, value in item_info.items():
                                    if key not in ['id', 'name_code', 'desc_code', 'name', 'desc']:
                                        f.write(f"{key}: {value}\n")
                                f.write("-" * 30 + "\n")
                    except Exception as e:
                        self.progress_text.append(f"카테고리 {category} 저장 중 오류: {str(e)}")
            
            # 아이템 정보 저장
            try:
                save_path = os.path.join(save_dir, 'items_info.txt')
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write("=== 아이템 정보 ===\n\n")
                    f.write(f"총 {len(results['categories']['items'])}개 항목\n")
                    f.write("-" * 50 + "\n\n")
                    
                    for item_id, item_info in results['categories']['items'].items():
                        f.write(f"ID: {item_id}\n")
                        if 'name_code' in item_info:
                            f.write(f"이름 코드: {item_info['name_code']}\n")
                            f.write(f"이름: {item_info['name']}\n")
                        if 'desc_code' in item_info:
                            f.write(f"설명 코드: {item_info['desc_code']}\n")
                            f.write(f"설명: {item_info['desc']}\n")
                        for key, value in item_info.items():
                            if key not in ['id', 'name_code', 'desc_code', 'name', 'desc']:
                                f.write(f"{key}: {value}\n")
                        f.write("-" * 30 + "\n")
            except Exception as e:
                self.progress_text.append(f"아이템 정보 저장 중 오류: {str(e)}")
            
            self.progress_text.append("\n처리가 완료되었습니다!")
            self.progress_text.append(f"결과가 다음 위치에 저장되었습니다:\n{save_dir}")
            os.startfile(save_dir)
            
        except Exception as e:
            self.progress_text.append(f"결과 저장 중 오류 발생: {str(e)}")

    def reset_all(self):
        """모든 데이터 초기화"""
        # 파일 리스트 초기화
        self.xml_files = []
        self.string_list.clear()
        self.item_list.clear()
        self.other_list.clear()
        
        # 진행바 초기화
        self.progress_bar.setValue(0)
        self.extract_progress_bar.setValue(0)
        
        # 텍스트 출력 초기화
        self.progress_text.clear()
        self.progress_text.append("초기화 완료")
        
        # 검색 결과 초기화
        self.search_result.clear()
        
        # worker 객체 초기화
        if hasattr(self, 'worker'):
            delattr(self, 'worker')
        
        # 검색 입력 초기화
        self.search_input.clear()

def main():
    app = QApplication(sys.argv)
    window = ItemExtractorGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 
