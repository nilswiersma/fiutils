import struct
import time
from typing import List

import serial


class Spider:
    _VERSION = 1.0

    CORE1 = 0
    CORE2 = 1

    HIGH_PRIORITY = 0
    LOW_PRIORITY = 1

    LOW_LEVEL = 0
    HIGH_LEVEL = 1

    RISING_EDGE = 0
    FALLING_EDGE = 1

    MAX_VLOGIC = 3.3
    MIN_VLOGIC = 0.0

    MIN_SEC = 8e-9
    MAX_SEC = 34.0

    MIN_TIMER = 1
    MAX_TIMER = 0x100000000

    MIN_VISIT = 1
    MAX_VISIT = 0x100000000

    MAX_VOLTAGE_OUT = 5.0
    MIN_VOLTAGE_OUT = 0

    MAX_GLITCH_OUT = 4.0
    MIN_GLITCH_OUT = -4.0

    MAX_PIN_INDEX = 31
    MIN_PIN_INDEX = 0

    VOLTAGE_OUT1 = 0
    VOLTAGE_OUT2 = 1
    VOLTAGE_OUT3 = 2
    VOLTAGE_OUT4 = 3
    VOLTAGE_OUT5 = 4
    VOLTAGE_OUT6 = 5

    FAST_CH1 = 0
    FAST_CH2 = 1

    UART1 = 0
    UART2 = 1

    MIN_BAUD = 1907
    MAX_BAUD = 15625000

    SPI_SNIFFER = 0
    I2C_SNIFFER = 1
    UART_SNIFFER = 2
    EMMC_SNIFFER = 3

    GLITCH_OUT1 = 0
    GLITCH_OUT2 = 1
    GLITCH_OUT_ALL = -1

    _BYTE_EQUAL = 1
    _BYTE_NOT_EQUAL = 0

    MAX_FIFO_DEPTH = 8192

    BIG_ENDIAN = 0
    LITTLE_ENDIAN = 1

    MIN_STATE_INDEX = 0
    MAX_STATE_INDEX = 255

    MAX_DATA_PATTERN_LENGTH = 256

    _MIN_COMPATIBLE_BITSTREAM = [1, 4]

    _ERROR_SDK_NOT_COMPATIBLE_WITH_DEVICE = (
        "\n\nSpider class is not compatible with current device firmware version {0}.{1}.\n"
        "The Spider class requires firmware version >= {2}.{3}.\n"
        "Check if the correct COM port has been used to instantiate Spider class, "
        "and then update the device firmware using installer "
        "'spider_bitstream_x.y.exe' located in '[sdk_installation]\\firmware' folder."
        )

    def __init__(self, index_machine, port: serial.Serial):
        self.DUMP_ON = False
        self._ser = port
        self._ser.timeout = 1.0
        self._opened = port.is_open
        self._index = index_machine
        self._select_machine(self._index)
        version = self.get_bitstream_version()
        if len(version) > 0:
            if version[0] <= self._MIN_COMPATIBLE_BITSTREAM[0]:
                if version[1] < self._MIN_COMPATIBLE_BITSTREAM[1]:
                    raise Exception(self._ERROR_SDK_NOT_COMPATIBLE_WITH_DEVICE.format(
                        version[0],
                        version[1],
                        self._MIN_COMPATIBLE_BITSTREAM[0],
                        self._MIN_COMPATIBLE_BITSTREAM[1]))

    def get_core_index(self) -> int:
        """
        Return the Spider Core index

        :return: the Spider Core index
        """

        return self._index

    def get_serial_number(self) -> int:
        """
        Return a 64-bit unique device serial number

        :return: a 64-bit unique device serial number
        """

        assert self._opened
        cmd = [0x00, 0x36]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = self._ser.read(8)

        return struct.unpack(">Q", din)[0]

    def _select_machine(self, i_fsm: int) -> None:
        """
        Select an FSM to receive commands

        :param i_fsm: the index of the state machine. One of 'Spider.CORE1' or 'Spider.CORE2'
        :return: None
        """

        assert self._opened
        cmd = [0x00, 0x0B, i_fsm & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def run_state(self) -> None:
        """
        Release the state machine to free-running

        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x01]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def hold_state(self) -> None:
        """
        Freeze the state machine in its current state

        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x02]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def force_state(self, state: int) -> None:
        """
        Jump state machine to any specified state

        :param state: the state index to jump to
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        state = int(state)
        cmd = [0x00, 0x03, state & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def set_input(self, state: int, index_pin: int) -> None:
        """
        When the specified state is reached, set the indexed pin to input

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.set_inputs(state, [index_pin])

    def set_inputs(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state is reached, set the indexed pins to inputs

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = b"\x00\x2F" + struct.pack(b">B", state & 0xFF) + struct.pack(b">I", mask)
        if self.DUMP_ON: print(f'_ser.write({cmd})')
        self._ser.write(cmd)

    def set_bit(self, state: int, index_pin: int) -> None:
        """
        When the specified state is reached, set the indexed pin to output and drive it high

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.set_bits(state, [index_pin])

    def set_bits(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state is reached, set the indexed pins to outputs and drive them high

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = b"\x00\x2D" + struct.pack(b">B", state & 0xFF) + struct.pack(b">I", mask)
        if self.DUMP_ON: print(f'_ser.write({cmd})')
        self._ser.write(cmd)

    def clr_bit(self, state: int, index_pin: int) -> None:
        """
        When the specified state is reached, set the indexed pin to output and drive it low

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.clr_bits(state, [index_pin])

    def clr_bits(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state is reached, set the indexed pins to outputs and drive them low

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = b"\x00\x2E" + struct.pack(b">B", state & 0xFF) + struct.pack(b">I", mask)
        if self.DUMP_ON: print(f'_ser.write({cmd})')
        self._ser.write(cmd)

    def use_output_fifo(self, state: int, index_pin: int) -> None:
        """
        When the specified state is reached, set the indexed pin to output and drive the pin with its Output FIFO

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.use_output_fifos(state, [index_pin])

    def use_output_fifos(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state is reached, set the indexed pins to outputs and drive them with its Output FIFOs

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = [0x00,
               0x31,
               state & 0xff,
               (mask >> 24) & 0xff,
               (mask >> 16) & 0xff,
               (mask >> 8) & 0xff,
               (mask >> 0) & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def push_input_fifo(self, state: int, index_pin: int) -> None:
        """
        When the specified state makes transition, push the value appears on the specified pin to its Input FIFO

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.push_input_fifos(state, [index_pin])

    def push_input_fifos(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state makes transition, push the values appears on the specified pins to their Input FIFO

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = [0x00,
               0x32,
               state & 0xff,
               0,
               0,
               0,
               0,
               (mask >> 24) & 0xff,
               (mask >> 16) & 0xff,
               (mask >> 8) & 0xff,
               (mask >> 0) & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def pop_output_fifo(self, state: int, index_pin: int) -> None:
        """
        When the specified state makes transition, pop the head-of-queue value out of the
        Output FIFO associated to the specified pin

        :param state: the state index
        :param index_pin: the pin index
        :return: None
        """

        self.pop_output_fifos(state, [index_pin])

    def pop_output_fifos(self, state: int, index_list: List[int]) -> None:
        """
        When the specified state makes transition, pop the head-of-queue values out of the
        Output FIFOs associated to the specified pins

        :param state: the state index
        :param index_list: the list of pin indices
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        mask = 0
        for index_pin in index_list:
            assert (self.MIN_PIN_INDEX <= index_pin <= self.MAX_PIN_INDEX)
            mask = mask | (1 << index_pin)
        cmd = [0x00,
               0x32,
               state & 0xff,
               (mask >> 24) & 0xff,
               (mask >> 16) & 0xff,
               (mask >> 8) & 0xff,
               (mask >> 0) & 0xff,
               0,
               0,
               0,
               0]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def write_fifo(self, val, wr_mask) -> None:
        """
        Write 1-bit value to each of the Output FIFO, if the corresponding write mask is set to '1'.
        Otherwise, the value is ignored.

        :param val: the value to set
        :param wr_mask: the write mask
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00,
               0x16,
               (val >> 24) & 0xff,
               (val >> 16) & 0xff,
               (val >> 8) & 0xff,
               val & 0xff,
               (wr_mask >> 24) & 0xff,
               (wr_mask >> 16) & 0xff,
               (wr_mask >> 8) & 0xff,
               wr_mask & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def write_fifo_lane(self, lane_index: int, data: List[int], bit_length: int, endianness: int) -> None:
        """
        Write a number of bits into a single selected FIFO lane

        :param lane_index: the index of the FIFO lane
        :param data: the data as a a list of bytes
        :param bit_length: the number of bits to write to the FIFO
        :param endianness: the bit order in which a byte will be serialized.
        :return: None
        """

        n_byte = (bit_length + 7) // 8
        assert self._opened
        assert (self.MIN_PIN_INDEX <= lane_index <= self.MAX_PIN_INDEX)
        assert (endianness == self.BIG_ENDIAN or endianness == self.LITTLE_ENDIAN)
        assert (bit_length <= self.MAX_FIFO_DEPTH)
        assert (len(data) == n_byte)

        if bit_length > 0:
            self._select_machine(self._index)
            cmd = [0x00,
                   0x34,
                   lane_index & 0xff,
                   endianness & 0xff,
                   (bit_length >> 8) & 0xff,
                   bit_length & 0xff] + data
            if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
            self._ser.write(bytes(cmd))

    def read_fifo(self, rd_mask: int) -> int:
        """
        Read 1-bit value from each of the Input FIFO, if the corresponding read mask is set,
        then the value will be popped after read

        :param rd_mask: the read mask
        :return: the value of the FIFO
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00,
               0x17,
               (rd_mask >> 24) & 0xff,
               (rd_mask >> 16) & 0xff,
               (rd_mask >> 8) & 0xff,
               rd_mask & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = list(bytes(self._ser.read(4)))
        return din[0] << 24 | din[1] << 16 | din[2] << 8 | din[3]

    def read_fifo_lane(self, lane_index: int, bit_length: int, endianness: int) -> List[int]:
        """
        Read a number of bits from a single selected FIFO lane

        :param lane_index: the index of the FIFO lane
        :param bit_length: the number of bits to read from the FIFO
        :param endianness: the bit order in which a byte will be serialized.
        :return: the values read from the FIFO
        """

        assert self._opened
        assert (self.MIN_PIN_INDEX <= lane_index <= self.MAX_PIN_INDEX)
        assert (endianness == self.BIG_ENDIAN or endianness == self.LITTLE_ENDIAN)
        assert (bit_length <= self.MAX_FIFO_DEPTH)

        if bit_length > 0:
            n_byte = (bit_length + 7) // 8
            self._select_machine(self._index)
            cmd = [0x00,
                   0x35,
                   (lane_index & 0xff),
                   endianness,
                   (bit_length >> 8) & 0xff,
                   bit_length & 0xff]
            if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
            self._ser.write(bytes(cmd))
            din = list(bytes(self._ser.read(n_byte)))

            return din
        else:
            return []

    def flush_fifo_lane(self, lane_index: int) -> None:
        """
        Flush a single lane of FIFO selected by the index

        :param lane_index: the FIFO lane index
        :return: None
        """

        assert self._opened
        assert (self.MIN_PIN_INDEX <= lane_index <= self.MAX_PIN_INDEX)
        self.flush_fifo(1 << lane_index)

    def flush_fifo_lanes(self, lane_indices: int) -> None:
        """
        Flush several lanes of FIFO selected by the indices

        :param lane_indices: the FIFO lanes to flush
        :return: None
        """

        assert self._opened
        assert (isinstance(lane_indices, list))
        mask = 0
        for lane_index in lane_indices:
            assert (self.MIN_PIN_INDEX <= lane_index <= self.MAX_PIN_INDEX)
            mask = mask | (1 << lane_index)
        self.flush_fifo(mask)

    def flush_fifo(self, clr_mask: int) -> None:
        """
        Flush Input and Output FIFOs, if the corresponding flush mask is set to '1',
        both Input and Output FIFO lanes are flushed.

        :param clr_mask: the mask for the FIFOs to flush
        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00,
               0x1C,
               (clr_mask >> 24) & 0xff,
               (clr_mask >> 16) & 0xff,
               (clr_mask >> 8) & 0xff,
               clr_mask & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def set_next_state(self, src_state: int, dst_state: int, priority: int) -> None:
        """
        Connect src_state to dst_state, using priority specified

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :return: None
        """

        assert self._opened
        assert (priority == self.HIGH_PRIORITY or priority == self.LOW_PRIORITY)
        self._select_machine(self._index)
        cmd = [0x00,
               0x05,
               priority,
               src_state & 0xff,
               dst_state & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def set_logic_level(self, v_logic: float) -> None:
        """
        Set IO pin voltage for logic '1'. For example, if set to 2.5 volts,
        then the logic '1' will be represented using 2.5 volts.

        :param v_logic: The voltage to be applied to the I/O lines, must be between 1.0 and 3.3 inclusive
        :return: None
        """

        assert self._opened
        assert (self.MIN_VLOGIC <= v_logic <= self.MAX_VLOGIC)
        data = int(v_logic / 5.0 * 0xffff)
        cmd = [0x01,
               0x02,
               (data >> 8) & 0xff,
               data & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    # Set the voltage value of the selected channel
    def set_voltage_out(self, ch: int, voltage: float) -> None:
        """
        Set the voltage value of the selected channel. Note that this value is not applied
        until commit_voltage is called.

        :param ch: The voltage channel. One of 'Spider.VOLTAGE_OUT_1' to 'Spider.MAX_VOLTAGE_OUT'
        :param voltage: the voltage level
        :return: None
        """

        assert self._opened
        assert (self.MIN_VOLTAGE_OUT <= voltage <= self.MAX_VOLTAGE_OUT)
        assert (self.VOLTAGE_OUT1 <= ch <= self.VOLTAGE_OUT6)
        data = int(voltage / 5.0 * 0xfff)
        cmd = [0x01,
               0x00,
               ch & 0xff,
               (data >> 8) & 0xff,
               data & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def commit_voltage(self) -> None:
        """
        Apply all voltages set through set_voltage_out

        :return: None
        """

        assert self._opened
        cmd = [0x01, 0x01]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def set_state_time_limit(self, state: int, **kwargs) -> None:
        """
        Update the timer overflow value of the specified state

        :param state: the state index
        :param kwargs: the value of the timer overflow, in 'seconds' or 'cycles', as specified
        :return: None
        """

        assert self._opened
        assert ('seconds' in kwargs or 'cycles' in kwargs), \
            "Must specify either 'seconds=' or 'cycles=' as keyword parameter."
        if 'seconds' in kwargs:
            assert (Spider.MIN_SEC <= kwargs['seconds'] <= Spider.MAX_SEC), \
                "Invalid time in seconds specified {0}. Valid value {1} ~ {2}."\
                .format(kwargs['seconds'], Spider.MIN_SEC, Spider.MAX_SEC)
            cycle = int(kwargs['seconds'] / Spider.MIN_SEC) - 1
        else:
            assert (Spider.MIN_TIMER <= kwargs['cycles'] <= Spider.MAX_TIMER), \
                "Invalid time in cycles specified {0}. Valid value {1} ~ {2}."\
                .format(kwargs['cycles'], Spider.MIN_TIMER, Spider.MAX_TIMER)
            cycle = int(kwargs['cycles'] - 1)
        self._select_machine(self._index)
        cmd = [0x00, 0x09, state & 0xff, (cycle >> 24) & 0xff, (cycle >> 16) & 0xff, (cycle >> 8) & 0xff, cycle & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def reset_settings(self) -> None:
        """
        Reset and clear the state machine, and jump to state 0

        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x0A, 0x00, 0x1B]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def match_transition(self, src_state: int, dst_state: int, priority: int) -> None:
        """
        Transition when a data pattern match is found by the sniffers

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :return: None
        """

        assert self._opened
        assert (priority == self.LOW_PRIORITY or priority == self.HIGH_PRIORITY)
        self._select_machine(self._index)

        mode = 2 | (32 << 4)
        cmd = [0x00,
               0x05,
               priority & 0xff,
               src_state & 0xff,
               dst_state & 0xff,
               0x00,
               0x07,
               priority & 0xff,
               src_state & 0xff,
               (mode >> 8) & 0xff,
               mode & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def disable_transition(self, target_state: int, priority: int) -> None:
        """
        Disable transition with the specified priority of the target state

        :param target_state: the target state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :return: None
        """

        assert self._opened
        assert (priority == self.LOW_PRIORITY or priority == self.HIGH_PRIORITY)
        self._select_machine(self._index)
        cmd = [0x00,
               0x07,
               priority & 0xFF,
               target_state & 0xFF,
               0x00,
               0x00]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def time_transition(self, src_state: int, dst_state: int, priority: int, **kwargs) -> None:
        """
        Transition when the specified time has elapsed in the src state

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :param kwargs: the value of the timer overflow, in 'seconds' or 'cycles', as specified
        :return: None
        """

        assert self._opened
        assert (priority == self.HIGH_PRIORITY or priority == self.LOW_PRIORITY)
        assert ('seconds' in kwargs or 'cycles' in kwargs), \
            "Must specify one of the keyword parameter 'seconds=' or 'cycles='."
        if 'seconds' in kwargs:
            transition_time = kwargs['seconds']
            assert (Spider.MIN_SEC <= transition_time <= Spider.MAX_SEC), \
                "Invalid time specified {0} seconds. Valid value {1} ~ {2}."\
                .format(transition_time, Spider.MIN_SEC, Spider.MAX_SEC)
            transition_time = int(transition_time / Spider.MIN_SEC) - 1
        else:
            cycles = kwargs['cycles']
            assert (Spider.MIN_TIMER <= cycles <= Spider.MAX_TIMER), \
                "Invalid cycle count specified {0}. Valid values {1} ~ {2}."\
                .format(cycles, Spider.MIN_TIMER, Spider.MAX_TIMER)
            transition_time = cycles - 1
        self._select_machine(self._index)
        cmd = [0x00,
               0x05,
               priority & 0xff,
               src_state & 0xff,
               dst_state & 0xff,
               0x00,
               0x07,
               priority & 0xff,
               src_state & 0xff,
               0x00,
               0x01,
               0x00,
               0x09,
               src_state & 0xff,
               (transition_time >> 24) & 0xff,
               (transition_time >> 16) & 0xff,
               (transition_time >> 8) & 0xff,
               transition_time & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def visit_transition(self, src_state: int, dst_state: int, priority: int, visit_limit: int) -> None:
        """
        Transition when the specified amount of visits has been paid to the src state

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :param visit_limit: the number of visits after which to transition
        :return: None
        """

        assert self._opened
        assert (priority == self.HIGH_PRIORITY or priority == self.LOW_PRIORITY)
        assert (self.MIN_VISIT <= visit_limit <= self.MAX_VISIT)
        self._select_machine(self._index)
        visit_limit = visit_limit - 1
        cmd = [0x00,
               0x05,
               priority & 0xff,
               src_state & 0xff,
               dst_state & 0xff,
               0x00,
               0x07,
               priority & 0xff,
               src_state & 0xff,
               0x00,
               0x03,
               0x00,
               0x19,
               src_state & 0xff,
               (visit_limit >> 24) & 0xff,
               (visit_limit >> 16) & 0xff,
               (visit_limit >> 8) & 0xff,
               visit_limit & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def level_transition(self, src_state: int, dst_state: int, priority: int, pin: int, level: int) -> None:
        """
        Transition when the specified level is observed on the specified pin

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :param pin: the pin index
        :param level: the trigger level. One of 'Spider.HIGH_LEVEL' or 'Spider.LOW_LEVEL'
        :return: None
        """

        assert self._opened
        assert (priority == self.HIGH_PRIORITY or priority == self.LOW_PRIORITY)
        assert (self.MIN_PIN_INDEX <= pin <= self.MAX_PIN_INDEX)
        assert (level == self.HIGH_LEVEL or level == self.LOW_LEVEL)
        self._select_machine(self._index)
        value = [0x0c, 0x08]
        mode = 2 | (pin << 4)
        mode = mode | value[level]
        cmd = [0x00,
               0x05,
               priority & 0xff,
               src_state & 0xff,
               dst_state & 0xff,
               0x00,
               0x07,
               priority & 0xff,
               src_state & 0xff,
               (mode >> 8) & 0xff,
               mode & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def edge_transition(self, src_state: int, dst_state: int, priority: int, pin: int, edge: int) -> None:
        """
        Transition when the specified edge is observed on the specified pin

        :param src_state: the source state index
        :param dst_state: the destination state index
        :param priority: the priority for the transition. One of 'Spider.LOW_PRIORITY' and 'Spider.HIGH_PRIORITY'
        :param pin: the pin index
        :param edge: the trigger level. One of 'Spider.RISING_EDGE' or 'Spider.FALLING_EDGE'
        :return: None
        """

        assert self._opened
        assert (priority == self.HIGH_PRIORITY or priority == self.LOW_PRIORITY)
        assert (self.MIN_PIN_INDEX <= pin <= self.MAX_PIN_INDEX)
        assert (edge == self.RISING_EDGE or edge == self.FALLING_EDGE)
        self._select_machine(self._index)
        value = [0, 4]
        mode = 2 | (pin << 4)
        mode = mode | value[edge]
        cmd = [0x00,
               0x05,
               priority & 0xff,
               src_state & 0xff,
               dst_state & 0xff,
               0x00,
               0x07,
               priority & 0xff,
               src_state & 0xff,
               (mode >> 8) & 0xff,
               mode & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    # Sample the values from all the 32 pins
    def get_pin_value(self) -> int:
        """
        Sample the values from all the 32 pins

        :return: the 32-bit value representing all 32 pin values
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x0F]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = list(bytes(self._ser.read(4)))
        return din[0] << 24 | din[1] << 16 | din[2] << 8 | din[3]

    def get_current_state(self) -> int:
        """
        Sample the current state the state machine is at

        :return: the current state index of the state machine
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x10]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = list(bytes(self._ser.read(1)))
        return din[0]

    def set_state_visit_limit(self, state: int, visit_limit: int) -> None:
        """
        Modify the visit limit associated to the specified state

        :param state: the index of the state to modify
        :param visit_limit: the new visit limit
        :return: None
        """

        assert self._opened
        assert (self.MIN_VISIT <= visit_limit <= self.MAX_VISIT)
        self._select_machine(self._index)
        visit_limit = visit_limit - 1
        cmd = [0x00,
               0x19,
               state & 0xff,
               (visit_limit >> 24) & 0xff,
               (visit_limit >> 16) & 0xff,
               (visit_limit >> 8) & 0xff,
               visit_limit & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def get_visit_counter(self, state: int) -> int:
        """
        Retrieve the number of visits paid to a state

        :param state: the index of the state
        :return: the current value of the visit counter
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x1A, state & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = list(bytes(self._ser.read(4)))
        return din[0] << 24 | din[1] << 16 | din[2] << 8 | din[3]

    def reset_visit_counters(self) -> None:
        """
        Reset the visit counter for all states

        :return: None
        """

        assert self._opened
        self._select_machine(self._index)
        cmd = [0x00, 0x1B]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def set_glitch_out(self, state: int, ch_sel: int, voltage: float) -> None:
        """
        When the specified state is reached, the specified voltage will appear on the selected high-speed channel

        :param state: the index of the state
        :param ch_sel: the glitch output to modify
        :param voltage: the new voltage level
        :return: None
        """

        ch_sel = int(ch_sel)
        assert self._opened
        assert (ch_sel == self.GLITCH_OUT1 or ch_sel == self.GLITCH_OUT2 or ch_sel == self.GLITCH_OUT_ALL)
        assert (self.MIN_GLITCH_OUT <= voltage <= self.MAX_GLITCH_OUT)

        if ch_sel == self.GLITCH_OUT_ALL:
            self.set_glitch_out(state, Spider.GLITCH_OUT1, voltage)
            self.set_glitch_out(state, Spider.GLITCH_OUT2, voltage)
        else:
            self._select_machine(self._index)
            voltage_a = voltage_b = voltage
            if voltage_a >= 0:
                data_a = int(voltage_a / 4.0 * 32767)
            else:
                data_a = int(voltage_a / 4.0 * 32768)

            if voltage_b >= 0:
                data_b = int(voltage_b / 4.0 * 32767)
            else:
                data_b = int(voltage_b / 4.0 * 32768)
            cmd = [0x00,
                   0x1E,
                   state & 0xff,
                   ch_sel & 0xff,
                   (data_a >> 8) & 0xff,
                   data_a & 0xff,
                   (data_b >> 8) & 0xff,
                   data_b & 0xff]
            if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
            self._ser.write(bytes(cmd))

    def set_glitch_out4ns(self, state: int, ch_sel: int, voltage_a: float, voltage_b: float) -> None:
        """
        When the specified state is reached, the specified voltage_a will be generated on the
        selected high-speed channel, and after 4ns voltage_b will be generated.

        :param state: the index of the state
        :param ch_sel: the glitch output to modify
        :param voltage_a: the new voltage level
        :param voltage_b: the new voltage level after 4ns
        :return: None
        """

        ch_sel = int(ch_sel)
        assert self._opened
        assert (ch_sel == self.GLITCH_OUT1 or ch_sel == self.GLITCH_OUT2 or ch_sel == self.GLITCH_OUT_ALL)
        assert (self.MIN_GLITCH_OUT <= voltage_a <= self.MAX_GLITCH_OUT)
        assert (self.MIN_GLITCH_OUT <= voltage_b <= self.MAX_GLITCH_OUT)

        if ch_sel == self.GLITCH_OUT_ALL:
            self.set_glitch_out4ns(state, Spider.GLITCH_OUT1, voltage_a, voltage_b)
            self.set_glitch_out4ns(state, Spider.GLITCH_OUT2, voltage_a, voltage_b)
        else:
            self._select_machine(self._index)

            if voltage_a >= 0:
                data_a = int(voltage_a / 4.0 * 32767)
            else:
                data_a = int(voltage_a / 4.0 * 32768)

            if voltage_b >= 0:
                data_b = int(voltage_b / 4.0 * 32767)
            else:
                data_b = int(voltage_b / 4.0 * 32768)
            cmd = [0x00,
                   0x1E,
                   state & 0xff,
                   ch_sel & 0xff,
                   (data_a >> 8) & 0xff,
                   data_a & 0xff,
                   (data_b >> 8) & 0xff,
                   data_b & 0xff]
            if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
            self._ser.write(bytes(cmd))

    def set_baudrate(self, sel_uart: int, baudrate: int) -> None:
        """
        Set the baudrate of selected UART channel

        :param sel_uart: the UART channel to modify
        :param baudrate: the new baudrate
        :return: None
        """

        assert self._opened
        assert (sel_uart == self.UART1 or sel_uart == self.UART2)
        assert self.MIN_BAUD <= baudrate <= self.MAX_BAUD

        tx_cnt = 65536 - int(125000000.0 / baudrate)
        rx_cnt = 65536 - int(15625000.0 / baudrate)
        cmd = [0x00,
               0x14,
               sel_uart,
               tx_cnt >> 8 & 0xff,
               tx_cnt & 0xff,
               rx_cnt >> 8 & 0xff,
               rx_cnt & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def flush_uart_queues(self, sel_uart: int) -> None:
        """
        Flush the TX/RX queues of the selected uart

        :param sel_uart: the UART channel
        :return: None
        """

        assert self._opened
        assert (sel_uart == self.UART1 or sel_uart == self.UART2)
        cmd = [0x00, 0x1F, sel_uart & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def uart_tx(self, sel_uart: int, data: List[int]) -> None:
        """
        Forward data through selected UART channel

        :param sel_uart: the UART channel
        :param data: the data to send
        :return: None
        """

        sel_uart = int(sel_uart)
        assert self._opened
        assert isinstance(data, list)
        assert (sel_uart == self.UART1 or sel_uart == self.UART2)
        cmd = [0x00, 0x0C, sel_uart & 0xff, 0, 0]
        tx_len = len(data)
        cmd[3] = tx_len >> 8 & 0xff
        cmd[4] = tx_len & 0xff
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        if self.DUMP_ON: print(f'_ser.write({bytes(data)})')
        self._ser.write(bytes(data))

    def uart_rx(self, sel_uart: int) -> List[int]:
        """
        Receive data through selected UART channel

        :param sel_uart: the UART channel
        :return: None
        """

        sel_uart = int(sel_uart)
        assert self._opened
        assert (sel_uart == self.UART1 or sel_uart == self.UART2)
        cmd = [0x00, 0x0E, sel_uart & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = list(bytes(self._ser.read(2)))
        din = (din[0] << 8) | din[1]
        if din > 0:
            din = list(bytes(self._ser.read(din)))
        else:
            din = []
        return din

    def set_sniffer_protocol(self, protocol: int) -> None:
        """
        Set protocol to Spider.SPI_SNIFFER for SPI sniffing(Default),
        set protocol to Spider.I2C_SNIFFER for I2C sniffing

        :param protocol: the protocol to select
        :return: None
        """

        protocol = int(protocol)
        assert self._opened
        assert (self.SPI_SNIFFER <= protocol <= self.EMMC_SNIFFER)
        cmd = bytes([0x00, 0x2C])
        cmd = cmd + struct.pack(b'>B', protocol)
        if self.DUMP_ON: print(f'_ser.write({cmd})')
        self._ser.write(cmd)

    def set_data_pattern(self, data_pattern: List[int]) -> None:
        """
        Define the data pattern that will trigger match_transition

        :param data_pattern: the data pattern to sniff
        :return: None
        """

        assert (isinstance(data_pattern, list)), "The data pattern must be specified with a list."
        assert (len(data_pattern) <= self.MAX_DATA_PATTERN_LENGTH), \
            "Invalid data pattern length specified {0}. Max. length is {1}"\
            .format(len(data_pattern), self.MAX_DATA_PATTERN_LENGTH)
        length = len(data_pattern)
        cmd = [0x00,
               0x21,
               ((length >> 24) & 0xFF),
               ((length >> 16) & 0xFF),
               ((length >> 8) & 0xFF),
               ((length >> 0) & 0xFF)] + data_pattern
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def sniff_bytes(self, n_byte: int, timeout_ms: int = 1000) -> List[int]:
        """
        Receive N bytes from the selected sniffing circuit

        :param n_byte: the number of bytes to receive
        :param timeout_ms: the timeout in ms (default 1000)
        :return: the list of sniffed bytes
        """

        n_byte = int(n_byte)
        timeout = float(timeout_ms) / 1000
        assert self._opened
        assert 0 < n_byte < 0x100000000
        assert 8e-9 < timeout <= 34.0
        self._ser.timeout = 1.0
        spider_timeout = int(timeout * 125e6)
        cmd = bytes([0x00, 0x2B])
        cmd = cmd + struct.pack(b'>I', n_byte) + struct.pack(b'>I', spider_timeout)
        if self.DUMP_ON: print(f'_ser.write({cmd})')
        self._ser.write(cmd)
        start = time.time()
        a = b""
        while True:
            tmp = self._ser.readall()
            a = a + tmp
            n_byte = n_byte - len(tmp)
            if len(tmp) != 0:
                start = time.time()
            end = time.time()
            if n_byte <= 0 or ((end - start) > timeout):
                break
        return list(struct.unpack("B" * len(a), a))

    def set_uart_sniffer_baudrate(self, baudrate: int) -> None:
        """
        Set the UART sniffer baudrate

        :param baudrate: the baudrate to set
        :return: None
        """

        assert (477 < baudrate < 1500000), "An invalid UART sniffer baudrate was specified."
        baud_int = 65536 - int(31250000 / baudrate)
        cmd = [0x00, 0x40, (baud_int >> 8) & 0xff, baud_int & 0xff]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def is_state_occupied(self, index_state: int) -> bool:
        """
        Check if a state has been configured, if configured, it is considered as occupied.

        :param index_state: the state index
        :return: True if the state is occupied, False otherwise
        """

        self._select_machine(self._index)
        cmd = [0x00, 0x37, index_state & 0xFF]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        din = self._ser.read(1)
        return list(bytes(din))[0] == 0x01

    def get_free_states(self, n_required_states: int) -> List[int]:
        """
        Try to find as many free states as indicated by n_required_states.

        :param n_required_states: the number of required states
        :return: the list of free states, or an empty list if no enough free states are available
        """

        free_states = []
        for i in range(0, Spider.MAX_STATE_INDEX + 1):
            if len(free_states) == n_required_states:
                for state in free_states:
                    self.disable_transition(state, Spider.HIGH_PRIORITY)
                    self.disable_transition(state, Spider.LOW_PRIORITY)
                return free_states
            else:
                if not self.is_state_occupied(i):
                    free_states.append(i)

        return []

    def free_state(self, index_state: int) -> None:
        """
        Reset the selected state and mark it as available

        :param index_state: the state index
        :return: None
        """

        self._select_machine(self._index)
        cmd = [0x00, 0x38, index_state & 0xFF]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def free_state_soft(self, index_state: int) -> None:
        """
        Reset the selected state without affecting the GPIO and glitch outputs

        :param index_state: the state index
        :return: None
        """

        self._select_machine(self._index)
        cmd = [0x00, 0x39, index_state & 0xFF]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))

    def sync(self) -> None:
        """
        Wait for the Spider device to send back an echo byte

        :return: None
        """

        assert self._opened
        cmd = [0x00, 0x20]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        data = self._ser.read(1)
        if data[0] != 0xd0:
            raise Exception("Out of Sync.")

    def wait_until_state(self, target_state: int, timeout_ms: int) -> int:
        """
        Wait for a target state to be reached within a specified timeout

        :param target_state: the target state index
        :param timeout_ms: the timeout in ms
        :return: 0 if target state is reached within timeout, otherwise -1.
        """

        start = time.time()
        target_state = target_state & 0xFF
        timeout_second = timeout_ms / 1000.0
        while True:
            cur_state = self.get_current_state()
            if cur_state == target_state:
                return 0
            if (time.time() - start) > timeout_second:
                return -1

    def wait_until_state_gt(self, target_state: int, timeout_ms: int) -> int:
        """
        Wait for a state, greater than the specified one, to be reached within timeout

        :param target_state: the target state index
        :param timeout_ms: the timeout in ms
        :return: 0 if target state is reached within timeout, otherwise -1.
        """

        start = time.time()
        target_state = target_state & 0xFF
        timeout_second = timeout_ms / 1000.0
        while True:
            cur_state = self.get_current_state()
            if cur_state > target_state:
                return 0
            if (time.time() - start) > timeout_second:
                return -1

    def wait_until_state_lt(self, target_state, timeout_ms):
        """
        Wait for a state, less than the specified one, to be reached within timeout

        :param target_state: the target state index
        :param timeout_ms: the timeout in ms
        :return: 0 if target state is reached within timeout, otherwise -1.
        """

        start = time.time()
        target_state = target_state & 0xFF
        timeout_second = timeout_ms / 1000.0
        while True:
            cur_state = self.get_current_state()
            if cur_state < target_state:
                return 0
            if (time.time() - start) > timeout_second:
                return -1

    def get_bitstream_version(self) -> List[int]:
        """
        Get the bitstream version

        :return: the bitstream version
        """

        cmd = [0xFF, 0x06]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        data = list(bytes(self._ser.read(2)))
        return data

    def get_build_id(self) -> int:
        """
        Get the build id

        :return: the build id
        """

        cmd = [0xFF, 0x08]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        data = self._ser.read(8)
        return struct.unpack(">Q", data)[0]

    def get_build_time(self) -> int:
        """
        Get the build time

        :return: the build time
        """

        cmd = [0xFF, 0x09]
        if self.DUMP_ON: print(f'_ser.write({bytes(cmd)})')
        self._ser.write(bytes(cmd))
        data = self._ser.read(4)
        build_time = struct.unpack(">I", data)[0]
        return build_time
