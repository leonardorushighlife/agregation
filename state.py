class State:
    def __init__(self, box_size: int):
        self.box_size = box_size
        self.box = 1
        self.in_box = 0
        self.wait_sscc = False

    def reset(self, box_size: int):
        self.box_size = box_size
        self.box = 1
        self.in_box = 0
        self.wait_sscc = False

    def scan_unit(self):
        if self.wait_sscc:
            return False

        self.in_box += 1

        if self.in_box >= self.box_size:
            self.wait_sscc = True
            return "WAIT_SSCC"

        return "UNIT_OK"

    def scan_sscc(self):
        if not self.wait_sscc:
            return False

        self.in_box = 0
        self.wait_sscc = False
        self.box += 1
        return "BOX_CLOSED"
