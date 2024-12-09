from .spider import Spider
import time


def _convert_to_nano_second(value):
    value = value * 1e9
    value = value - value % 4
    return value


class Chronology:
    """
    This class provides a simplified, higher level API for defining glitch sequences with the Spider.

    The Chronology class defines simple Actions (e.g. setting GPIO or analog values) and Events.
    With these Actions and Events, the user can define a glitch sequence and the Chronology class will generate the
    Spider state machine configuration for this glitch sequence.

    Note that within the Chronology API docs glitch sequence is not to be confused with the more broad
    meaning of Sequence used in other parts of Inspector (such as acquisition sequences or
    perturbation sequences).

    About the name: The Chronology class is suitable for cases in which the state diagram of the state machine takes
    the form of a linear graph - that means no loops or branches in the graph, and each state is connected to
    the next in Chronological order.
    """

    MIN_TRIGGER_COUNT = 1
    MAX_TRIGGER_COUNT = 0xfffffffe
    _INVALID_PIN_INDEX = \
        "An invalid pin index was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_TRIGGER_WAIT_COUNT = \
        "An invalid trigger wait count was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_WAIT_CYCLE = \
        "An invalid amount of cycles was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_VOLTAGE = \
        "An invalid voltage was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_GLITCH_OUT = \
        "An invalid glitch output was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_TIME = \
        "An invalid amount of time was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_VOUT_INDEX = \
        "An invalid voltage output was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _INVALID_POWER_PERCENTAGE = \
        "An invalid power percentage was specified: {0}. Valid value range {1} ~ {2} inclusive."
    _MIN_POWER = 0
    _MAX_POWER = 100

    def __init__(self, spider):
        self._state_list = []
        self._name_list = []
        self._spider: Spider = spider
        self._now_state = self._spider.get_free_states(1)[0]
        self._idle_state = self._spider.get_free_states(1)[0]
        self._spider.disable_transition(self._now_state, Spider.HIGH_PRIORITY)
        self._spider.disable_transition(self._now_state, Spider.LOW_PRIORITY)
        self._spider.disable_transition(self._idle_state, Spider.HIGH_PRIORITY)
        self._spider.disable_transition(self._idle_state, Spider.LOW_PRIORITY)
        self._normal_vcc = [0.0, 0.0]

    def set_power_now(self, index_voltage_out: int, power_percentage: int) -> None:
        """
        Sets a voltage on one of the "slow" Voltage outputs immediately.

        The changed output voltage will be effective immediately, however
        there is no guaranteed timing.
        This function is safe to use while a glitch sequence is running.

        This method is meant to be used from the Voltage Output port connected to an
        EMFI transient module or a Diode Laser module.

        :param index_voltage_out: Spider voltage output port number.
        One value out of range [Spider.VOLTAGE_OUT1..Spider.VOLTAGE_OUT6]
        :param power_percentage: Voltage value as percentage [0..100] of the max value (3.3 V)
        :return: None
        """

        assert index_voltage_out >= Spider.VOLTAGE_OUT1 & index_voltage_out <= Spider.VOLTAGE_OUT6, \
            self._INVALID_VOUT_INDEX.format(index_voltage_out, Spider.VOLTAGE_OUT1, Spider.VOLTAGE_OUT6)
        assert power_percentage >= 0 & power_percentage <= 100, \
            self._INVALID_POWER_PERCENTAGE.format(power_percentage, self._MIN_POWER, self._MAX_POWER)
        voltage = 3.3 * (power_percentage / self._MAX_POWER)
        self._spider.set_voltage_out(index_voltage_out, voltage)
        self._spider.commit_voltage()

    def wait_trigger(self, pin_index: int, sensitivity: int, count: int) -> int:
        """
        Suspend glitch sequence execution until trigger event occurs.

        Once the glitch sequence is at this step, it will wait for either a rising or falling edge
        (specified by sensitivity) to occur count times on Pin[pin_index] before
        proceeding to the next glitch sequence step.

        The function returns the ID of the glitch sequence step. This ID can be used together with the
        Chronology.get_current_state() method to check whether the Trigger event occurred:
        If the trigger event happened and the glitch sequence has moved on,
        Id_returned_by_wait_trigger == chronology.get_current_state() will evaluate to `False`.

        :param pin_index: Number of the GPIO pin to trigger on
        :param sensitivity: One of 'Spider.RISING_EDGE' or 'Spider.FALLING_EDGE'
        :param count: Number of times the edge event has to occur before proceeding to next step
        :return: ID of the added wait step
        """

        assert Spider.MIN_PIN_INDEX <= pin_index <= Spider.MAX_PIN_INDEX, self._INVALID_PIN_INDEX\
            .format(pin_index, Spider.MIN_PIN_INDEX, Spider.MAX_PIN_INDEX)
        assert 0 < count < 0xfffffffe, self._INVALID_TRIGGER_WAIT_COUNT\
            .format(count, self.MIN_TRIGGER_COUNT, self.MAX_TRIGGER_COUNT)
        last_state = self._get_last_state("WAIT_TRIGGER")
        self._spider.edge_transition(last_state, last_state, Spider.LOW_PRIORITY, pin_index, sensitivity)
        new_state = self._get_new_state()
        # Increment visit limit by 1
        self._spider.visit_transition(last_state, new_state, Spider.HIGH_PRIORITY, count + 1)
        return last_state

    def set_gpio(self, pin_index: int, value: int) -> None:
        """
        Add a glitch sequence step that sets a GPIO pin to a specified value.

        *Note: This does not set the GPIO output immediately.* If you want to set
        the GPIO output value immediately see Chronology.set_gpio_now(int, int) instead

        :param pin_index: Number of the GPIO pin to set.
        One value out of range ['Spider.MIN_PIN_INDEX'..'Spider.MAX_PIN_INDEX']
        :param value: 1 or 0
        :return: None
        """

        assert Spider.MIN_PIN_INDEX <= pin_index <= Spider.MAX_PIN_INDEX, self._INVALID_PIN_INDEX\
            .format(pin_index, Spider.MIN_PIN_INDEX, Spider.MAX_PIN_INDEX)
        last_state = self._get_last_state("SETGPIO:" + str(value))
        if value & 1 == 0:
            self._spider.clr_bit(last_state, pin_index)
        else:
            self._spider.set_bit(last_state, pin_index)
        new_state = self._get_new_state()
        self._spider.time_transition(last_state, new_state, Spider.HIGH_PRIORITY, cycles=1)

    def set_gpio_now(self, pin_index: int, value: int) -> None:
        """
        Set a GPIO Pin to high or low immediately.

        Note: This sets the GPIO output *immediately*. If you want to add a glitch sequence step that changes
        the GPIO output value see 'Chronology.set_gpio(int, int)' instead.

        *Note: This is not safe to call while a glitch sequence is running.* Either call this method before
        calling 'Chronology.start()' or after 'Chronology.wait_until_finish(int)' has signalled the
        completion of the glitch sequence.

        :param pin_index: Number of the GPIO pin for to set.
        One value out of range ['Spider.MIN_PIN_INDEX'..'Spider.MAX_PIN_INDEX']
        :param value: 1 or 0
        :return: None
        """

        assert Spider.MIN_PIN_INDEX <= pin_index <= Spider.MAX_PIN_INDEX, self._INVALID_PIN_INDEX\
            .format(pin_index, Spider.MIN_PIN_INDEX, Spider.MAX_PIN_INDEX)
        current_state = self._spider.get_current_state()

        if value & 1 == 0:
            self._spider.clr_bit(self._now_state, pin_index)
        else:
            self._spider.set_bit(self._now_state, pin_index)
        self._spider.time_transition(self._now_state, current_state, Spider.HIGH_PRIORITY, cycles=1)
        self._spider.force_state(self._now_state)

    def wait_time(self, time_sec: float) -> None:
        """
        Suspend glitch sequence execution for the specified amount of seconds

        :param time_sec: Time to wait until the glitch sequence will be continued.
        Range ['Spider.MIN_SEC', 'Spider.MAX_SEC']
        :return: None
        """

        assert Spider.MIN_SEC <= time_sec <= Spider.MAX_SEC, self._INVALID_TIME\
            .format(time_sec, Spider.MIN_SEC, Spider.MAX_SEC)
        last_state = self._get_last_state("WAIT_TIME(SEC): " + str(time_sec))
        new_state = self._get_new_state()

        self._spider.time_transition(last_state, new_state, Spider.HIGH_PRIORITY, seconds=time_sec)

    def set_vcc(self, index_glitch_out: int, voltage: float) -> None:
        """
        Set the voltage to output on a Glitch Out port and the post-glitch voltage.

        *Note: This does not set the output value immediately.* If you want to set
        the Glitch Output value immediately see 'Chronology.set_vcc_now(int, float)' instead

        :param index_glitch_out: Glitch Output number.
        One of 'Spider.GLITCH_OUT1' or 'Spider.GLITCH_OUT2'
        :param voltage: Voltage to set on the selected output
        :return: None
        """

        assert 0.0 <= voltage <= Spider.MAX_GLITCH_OUT, self._INVALID_VOLTAGE\
            .format(voltage, 0.0, Spider.MAX_GLITCH_OUT)
        assert Spider.GLITCH_OUT1 <= index_glitch_out <= Spider.GLITCH_OUT2, self._INVALID_GLITCH_OUT\
            .format(index_glitch_out, Spider.GLITCH_OUT1, Spider.GLITCH_OUT2)
        last_state = self._get_last_state("SET VCC: " + str(voltage))
        self._spider.set_glitch_out(last_state, index_glitch_out, voltage)
        new_state = self._get_new_state()
        self._spider.time_transition(last_state, new_state, Spider.HIGH_PRIORITY, cycles=1)
        self._normal_vcc[index_glitch_out] = voltage

    def set_vcc_now(self, index_glitch_out: int, voltage: float) -> None:
        """
        Set a voltage to output on a Glitch Out port and the post-glitch voltage immediately.

        In contrast to 'Chronology.set_glitch_out_now(int, float)' this will also set the post-glitch voltage
        value. After a call to 'Chronology.glitch(int, float, float, float)' the output will be
        restored to the last value that was set by this function or by
        'Chronology.set_vcc(int, float)'.

        *Note: This is not safe to call while a glitch sequence is running.* Either call this method before
        calling 'Chronology.start()' or after 'Chronology.wait_until_finish(int)' has signalled the
        completion of the glitch sequence

        :param index_glitch_out: Glitch Output number. One of 'Spider.GLITCH_OUT1' or 'Spider.GLITCH_OUT2'
        :param voltage: Voltage to set on the selected output
        :return: None
        """

        assert 0.0 <= voltage <= Spider.MAX_GLITCH_OUT, self._INVALID_VOLTAGE\
            .format(voltage, 0.0, Spider.MAX_GLITCH_OUT)
        assert Spider.GLITCH_OUT1 <= index_glitch_out <= Spider.GLITCH_OUT2, self._INVALID_GLITCH_OUT\
            .format(index_glitch_out, Spider.GLITCH_OUT1, Spider.GLITCH_OUT2)
        self.set_glitch_out_now(index_glitch_out, voltage)
        self._normal_vcc[index_glitch_out] = voltage

    def set_glitch_out_now(self, index_glitch_out: int, voltage: float) -> None:
        """
        Set the voltage to output on a Glitch Out port immediately.

        In contrast to 'Chronology.set_vcc_now(int, float)' this will not set the post-glitch voltage
        value. After a call to 'Chronology.glitch(int, float, float, float)' the output will be
        restored to the last value that was set by 'Chronology.set_vcc_now(int, float)' or
        'Chronology.set_vcc(int, float)'.

        *Note: This is not safe to call while a glitch sequence is running.* Either call this method before
        calling 'Chronology.start()' or after 'Chronology.wait_until_finish(int)' has signalled the
        completion of the glitch sequence

        :param index_glitch_out: Glitch Output number. One of 'Spider.GLITCH_OUT1' or 'Spider.GLITCH_OUT2'
        :param voltage: Voltage to set on the selected output
        :return: None
        """

        assert Spider.GLITCH_OUT1 <= index_glitch_out <= Spider.GLITCH_OUT2, self._INVALID_GLITCH_OUT\
            .format(index_glitch_out, Spider.GLITCH_OUT1, Spider.GLITCH_OUT2)
        current_state = self._spider.get_current_state()
        self._spider.set_glitch_out(self._now_state, index_glitch_out, voltage)
        self._spider.time_transition(self._now_state, current_state, Spider.HIGH_PRIORITY, cycles=1)
        self._spider.force_state(self._now_state)

    def glitch(self, index_glitch_out: int, glitch_vcc: float, wait_time: float, glitch_time: float) -> None:
        """
        Add a glitch pulse glitch sequence step.

        When the glitch sequence executes this step, a glitch pulse will be applied on the specified output.
        The timing and pulsed value can be specified. After the glitch the output voltage will return to its pre-pulse
        value.

        *Note: The normal_vcc value is set by 'Chronology.set_vcc(int, float)' or
        'Chronology.set_vcc_now(int, float)'*

        *Note: The wait_time_s and glitch_time_s will be rounded down to the nearest multiple of 4
        nanoseconds.*

        :param index_glitch_out: Glitch Output number. One of 'Spider.GLITCH_OUT1' or 'Spider.GLITCH_OUT2'
        :param glitch_vcc: Output voltage while glitch is active
        :param wait_time: Time delay from begin of execution of this step, until the glitch pulsed voltage is applied.
                        Range ['Spider.MIN_SEC', 'Spider.MAX_SEC']
        :param glitch_time: Width of the pulse. Range ['Spider.MIN_SEC', 'Spider.MAX_SEC']
        :return: None
        """

        assert Spider.GLITCH_OUT1 <= index_glitch_out <= Spider.GLITCH_OUT2, self._INVALID_GLITCH_OUT\
            .format(index_glitch_out, Spider.GLITCH_OUT1, Spider.GLITCH_OUT2)
        assert 0.0 <= wait_time <= Spider.MAX_SEC, self._INVALID_TIME.format(wait_time, 0.0, Spider.MAX_SEC)
        assert 0.0 <= glitch_time <= Spider.MAX_SEC, self._INVALID_TIME.format(glitch_time, 0.0, Spider.MAX_SEC)

        orig_wait_time = wait_time
        orig_glitch_time = glitch_time
        wait_time = int(_convert_to_nano_second(wait_time))
        glitch_time = int(_convert_to_nano_second(glitch_time))

        symbols = self._allocate_state(wait_time, glitch_time)

        tmp_state_list = self._spider.get_free_states(len(symbols))
        assert len(tmp_state_list) == len(symbols), \
            "Spider CORE{0} does not have enough free states to accommodate this machine."\
            .format(self._spider.get_core_index() + 1)

        last_state = self._get_last_state("START GLITCH, WAIT(Sec):{0}, GLITCH(Sec):{1}"
                                          .format(orig_wait_time, orig_glitch_time))
        self._add_states(tmp_state_list)

        for i in range(0, len(tmp_state_list)):
            if i == 0:
                src = last_state
            else:
                src = tmp_state_list[i - 1]

            dst = tmp_state_list[i]

            self._spider.disable_transition(src, Spider.LOW_PRIORITY)
            if symbols[i] == 0:
                n_cycles = wait_time // 8
            elif symbols[i] == 2:
                n_cycles = glitch_time // 8
                self._spider.set_glitch_out(src, index_glitch_out, glitch_vcc)
            elif symbols[i] == 1:
                n_cycles = 1
                self._spider.set_glitch_out4ns(src, index_glitch_out, self._normal_vcc[index_glitch_out], glitch_vcc)
                glitch_time -= 4
            else:
                n_cycles = 1
                self._spider.set_glitch_out4ns(src, index_glitch_out, glitch_vcc, self._normal_vcc[index_glitch_out])
            self._spider.time_transition(src, dst, Spider.HIGH_PRIORITY, cycles=n_cycles)
            if i == (len(tmp_state_list) - 1):
                self._spider.set_glitch_out(dst, index_glitch_out, self._normal_vcc[index_glitch_out])

    def start(self) -> None:
        """
        Start glitch sequence execution.

        If a glitch sequence is running it is stopped and the glitch sequence of this Chronology
        instance is started instead

        :return: None
        """

        if len(self._state_list) != 0:
            self._spider.run_state()
            self._spider.force_state(self._state_list[0])

    def wait_until_finish(self, timeout_ms: int) -> bool:
        """
        Blocks until glitch sequence completion or timeout

        :param timeout_ms: max time to wait for the glitch sequence to finish
        :return: True if wait timed out, otherwise False
        """

        timeout_ms = timeout_ms / 1000.0
        if len(self._state_list) == 0:
            return False
        else:
            begin = time.perf_counter()
            while (time.perf_counter() - begin) <= timeout_ms:
                if self._spider.get_current_state() == self._state_list[-1]:
                    return False
            return True

    def forget_events(self) -> None:
        """
        Stops the glitch sequence execution and clears the glitch sequence that this Chronology instance contains

        :return:
        """

        for state in self._state_list:
            self._spider.free_state(state)
        self._state_list = []
        self._name_list = []
        self._spider.disable_transition(self._now_state, Spider.HIGH_PRIORITY)
        self._spider.disable_transition(self._now_state, Spider.LOW_PRIORITY)
        self._spider.force_state(self._idle_state)
        self._spider.sync()
        self._spider.run_state()

    def get_current_state(self) -> None:
        """
        Get the step that the Spider state machine is currently in.

        *Note: Do not rely on this information while the glitch sequence is running.* The glitch sequence may
        have moved on to the next step. Either call this method before calling 'Chronology.start()' or after
        'Chronology.wait_until_finish(int)' has signalled the completion of the glitch sequence.

        An exception to this advise is the usage as described in 'Chronology.waitTrigger(int, int, int)'

        :return:
        """

        return self._spider.get_current_state()

    def report_events(self) -> None:
        """
        Prints information about the glitch sequence that this Chronology instance describes to stdout

        :return: None
        """

        for name, state in zip(self._name_list, self._state_list):
            print("S{0} {1}".format(state, name))

    def _assign_new_desc(self, description):
        self._name_list.append(description)

    def _get_last_state(self, description):
        if len(self._state_list) == 0:
            self._get_new_state()
        self._name_list[-1] = description

        return self._state_list[-1]

    def _get_new_state(self):
        new_state = self._spider.get_free_states(1)[0]
        self._spider.disable_transition(new_state, Spider.HIGH_PRIORITY)
        self._spider.disable_transition(new_state, Spider.LOW_PRIORITY)
        self._state_list.append(new_state)
        self._assign_new_desc("NOP")

        return self._state_list[-1]

    def _add_states(self, state_list):
        tmp_list = ["CONTINUED GLITCH"] * len(state_list)

        self._state_list = self._state_list + state_list
        self._name_list = self._name_list + tmp_list

    @staticmethod
    def _allocate_state(wait_time, glitch_time):
        wait_states = []
        glitch_states = []

        if wait_time < 4:
            pass  # Do nothing
        elif wait_time < 8:
            wait_states.append(1)  # Need only WAIT_FRAG
            glitch_time = glitch_time - 4
        elif wait_time % 8 >= 4:
            wait_states.append(0)  # Need both WAIT and WAIT_FRAG
            wait_states.append(1)
            glitch_time = glitch_time - 4
        else:
            wait_states.append(0)  # Need only WAIT

        if glitch_time < 4:
            pass
        elif glitch_time < 8:
            glitch_states.append(3)  # Need only GLITCH_FRAG
        elif glitch_time % 8 >= 4:
            glitch_states.append(2)  # Need both GLITCH and GLITCH_FRAG
            glitch_states.append(3)
        else:
            glitch_states.append(2)  # Need only Glitch

        return wait_states + glitch_states
