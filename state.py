class State:
    def __init__(self, box_size: int, pallet_size: int = 110):
        self.box_size = box_size
        self.pallet_size = pallet_size
        self.box = 1
        self.in_box = 0
        self.pallet = 1
        self.in_pallet = 0
        self.wait_sscc = False
        self.wait_pallet_sscc = False

    def reset(self, box_size: int, pallet_size: int = 110):
        self.box_size = box_size
        self.pallet_size = pallet_size
        self.box = 1
        self.in_box = 0
        self.pallet = 1
        self.in_pallet = 0
        self.wait_sscc = False
        self.wait_pallet_sscc = False

    def scan_unit(self):
        if self.wait_sscc or self.wait_pallet_sscc:
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
        self.in_pallet += 1

        if self.in_pallet >= self.pallet_size:
            self.wait_pallet_sscc = True
            return "WAIT_PALLET_SSCC"

        return "BOX_CLOSED"

    def scan_pallet_sscc(self):
        if not self.wait_pallet_sscc:
            return False

        self.in_pallet = 0
        self.wait_pallet_sscc = False
        self.pallet += 1
        return "PALLET_CLOSED"
