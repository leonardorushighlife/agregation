from datetime import datetime

class State:
    def __init__(self, box_size: int):
        self.box_size = box_size
        self.reset(box_size)

    def reset(self, box_size: int):
        self.box_size = box_size
        self.box = 1
        self.in_box = 0
        self.wait_sscc = False
        self.current_box_units = []
        self.boxes_data = []         # Список (sscc, [unit_data])
        self.duplicates_list = []    # Список найденных дубликатов для отчета
        self.shift_start_time = datetime.now()
        self.total_codes_in_shift = 0

    def load_recovery(self, boxes):
        """Загрузка данных из БД после сбоя"""
        self.boxes_data = boxes
        self.box = len(boxes) + 1
        self.total_codes_in_shift = sum(len(units) for _, units in boxes)

    def scan_unit(self, parsed_data: dict):
        if self.wait_sscc: return False
        self.current_box_units.append(parsed_data)
        self.in_box += 1
        self.total_codes_in_shift += 1
        if self.in_box >= self.box_size:
            self.wait_sscc = True
            return "WAIT_SSCC"
        return "UNIT_OK"

    def scan_sscc(self, sscc: str):
        if not self.wait_sscc: return False
        self.boxes_data.append((sscc, self.current_box_units))
        last_units = self.current_box_units
        self.current_box_units = []
        self.in_box = 0
        self.wait_sscc = False
        self.box += 1
        return last_units # Возвращаем юниты для записи в БД

    def get_shift_summary(self):
        return {
            "start_time": self.shift_start_time,
            "total_boxes": len(self.boxes_data),
            "total_codes": self.total_codes_in_shift,
            "data": self.boxes_data,
            "duplicates": self.duplicates_list
        }
