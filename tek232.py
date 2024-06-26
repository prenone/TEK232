from enum import Enum
import webbrowser
import numpy as np
import dearpygui.dearpygui as dpg
from dpg_themes import create_theme_imgui_light
import pyperclip
from matplotlib import pyplot as plt


class OscilloscopeChannel(Enum):
    CH1 = "CH1"
    CH2 = "CH2"

class OscilloscopeMeasurementType(Enum):
    PeakToPeak = "PK2PK"
    Frequency = "FREQ"
    Period = "PERI"
    Maximum = "MAXI"
    Minimum = "MINI"
    
class CurveType(Enum):
    Oscilloscope = "OSCILLOSCOPE"
    TrueVoltage = "TRUE_VOLTAGE"

def OscilloscopeSendCommand(ser, message):
    with open(usbtmc_port, "r+") as ser:
        ser.write(f"{message}\n")
        ser.flush()
    gui_add_to_log(f"-> {message}\n")
    
    
def OscilloscopeSendCommandAndRead(ser, message):
    with open(usbtmc_port, "r+") as ser:
        ser.write(f"{message}\n")
        ser.flush()
        res = ser.readline()
        
        
    gui_add_to_log(f"-> {message}\n")
    gui_add_to_log(f"<- {res}\n")
    
    return res


def OscilloscopeId(ser):
    id = OscilloscopeSendCommandAndRead(ser, f"ID?")
    
    return id

def OscilloscopeAlle(ser):
    alle = OscilloscopeSendCommandAndRead(ser, f"ALLE?")
    
    return alle

def OscilloscopeImmediateMeasure(ser, channel: OscilloscopeChannel, type: OscilloscopeMeasurementType):
    
    OscilloscopeSendCommand(ser, f"MEASU:IMM:SOU {channel.value}")
    OscilloscopeSendCommand(ser, f"MEASU:IMM:TYPE {type.value}")
    
    value = OscilloscopeSendCommandAndRead(ser, f"MEASU:IMM:VAL?")
    
    unit_str = OscilloscopeSendCommandAndRead(ser, f"MEASU:IMM:UNI?")
     
    return (value, unit_str)

def OscilloscopeCurve(ser, channel: OscilloscopeChannel):
    
    OscilloscopeSendCommand(ser, f"DAT:ENC ASCII")
    OscilloscopeSendCommand(ser, f"DAT:SOU {channel.value}")
    OscilloscopeSendCommand(ser, f"DAT:START 1")
    OscilloscopeSendCommand(ser, f"DAT:STOP 2500")
    OscilloscopeSendCommand(ser, f"DAT:WID 2")
    
    curve_str = OscilloscopeSendCommandAndRead(ser, f"CURV?")
    
    info_str = OscilloscopeSendCommandAndRead(ser, f"WFMP:WFI?")
    
    xaxis_info = info_str.split(", ")[3]
    yaxis_info = info_str.split(", ")[2]
    
    volts_per_div = float(yaxis_info.split(" ")[0])
    seconds_per_div = float(xaxis_info.split(" ")[0])

    points = np.array([int(point) for point in curve_str.split(",")])
    
    voltage = (points / 32768 * 10) * volts_per_div
    time = np.arange(0, 2500, 1) / 2500 * 10 * seconds_per_div
    
    return np.array([time, points, voltage]).T


ser = None
usbtmc_port = None

def gui_rs232_connect():
    global ser
    global usbtmc_port
    
    usbtmc_port = dpg.get_value("usbtmc_file_input")
    
    dpg.configure_item("usbtmc_file_window", show=False)
    dpg.configure_item("communication_log_window", show=True)
    dpg.configure_item("oscilloscope_commands_window", show=True)
    
    OscilloscopeId(ser)
    

communication_log_str = ""

def gui_add_to_log(message):
    global communication_log_str
    communication_log_str = communication_log_str + message
    
    dpg.set_value("communication_log_text", communication_log_str)
    dpg.set_item_height("communication_log_text", dpg.get_text_size(communication_log_str)[1] + (2 * 3))
    
    
def gui_immediate_measurement(mw_index):
    channel = OscilloscopeChannel(dpg.get_value(f"measurement_channel_combo_{mw_index}"))
    type = OscilloscopeMeasurementType(dpg.get_value(f"measurement_type_combo_{mw_index}"))
    
    measure = OscilloscopeImmediateMeasure(ser, channel, type)
    
    dpg.set_value(f"measurement_text_{mw_index}", f"{measure[0]} {measure[1]}")
    

acquisitions = []

def gui_curve_acquisition(cw_index, channels):
    for channel in channels:
        acquisitions[cw_index][0 if channel == OscilloscopeChannel.CH1 else 1] = OscilloscopeCurve(ser, channel).T
    
    gui_update_curve_plot(cw_index)


def gui_update_curve_plot(cw_index):
    if dpg.get_value(f"curve_type_combo_{cw_index}") == CurveType.Oscilloscope.value:
        dpg.configure_item(f"y_curve_axis_{cw_index}", label="Read")
        curve_type = 1
    else:
        dpg.configure_item(f"y_curve_axis_{cw_index}", label="Voltage [V]")
        curve_type = 2
    
    dpg.set_value(f"curve_series_1_{cw_index}", [acquisitions[cw_index][0][0], acquisitions[cw_index][0][curve_type]])
    dpg.set_value(f"curve_series_2_{cw_index}", [acquisitions[cw_index][1][0], acquisitions[cw_index][1][curve_type]])
    
    dpg.fit_axis_data(f"x_curve_axis_{cw_index}")
    dpg.fit_axis_data(f"y_curve_axis_{cw_index}")
    

def gui_save_curve_plot(cw_index):
    plt.close()
    
    if dpg.get_value(f"curve_type_combo_{cw_index}") == CurveType.Oscilloscope.value:
        plt.ylabel("Read")
        curve_type = 1
    else:
        plt.ylabel("Voltage [V]")
        curve_type = 2
        
    plt.plot(acquisitions[cw_index][0][0], acquisitions[cw_index][0][curve_type], label="CH1")
    plt.plot(acquisitions[cw_index][1][0], acquisitions[cw_index][1][curve_type], label="CH2")
    
    plt.xlabel("Time [s]")
    plt.grid()
    
    plt.legend()
    
    def save_file(sender, app_data):
        plt.savefig(app_data["file_path_name"])
    
    dpg.delete_item("curve_save_dialog")
    with dpg.file_dialog(directory_selector=False, show=True, callback=save_file, default_filename=f"curve_{cw_index}.pdf", tag="curve_save_dialog", width=700 ,height=400):
        dpg.add_file_extension(".*")
        dpg.add_file_extension(".pdf")
        dpg.add_file_extension(".png")
        dpg.add_file_extension(".jpg")

def gui_save_curve_csv(cw_index):
    time = acquisitions[cw_index][0][0]
    ch1_read =  acquisitions[cw_index][0][1]
    ch2_read =  acquisitions[cw_index][1][1]
    ch1_voltage =  acquisitions[cw_index][0][2]
    ch2_voltage =  acquisitions[cw_index][1][2]
    
    csv_array = np.asarray([time, ch1_read, ch2_read, ch1_voltage, ch2_voltage])
    
    def save_file(sender, app_data):
        np.savetxt(app_data["file_path_name"], csv_array.T, delimiter=",", header="Time [s], Read CH1, Read CH2, Voltage CH1 [V], Voltage CH2 [V    ]")
    
    dpg.delete_item("csv_save_dialog")
    with dpg.file_dialog(directory_selector=False, show=True, callback=save_file, default_filename=f"curve_{cw_index}.csv", tag="csv_save_dialog", width=700 ,height=400):
        dpg.add_file_extension(".*")
        dpg.add_file_extension(".csv")
        dpg.add_file_extension(".txt")

dpg.create_context()
dpg.create_viewport(title="TEK-232 Oscilloscope Utilities", clear_color=[239,228,208,255], large_icon="oscilloscope.jpg")
dpg.setup_dearpygui()

theme = create_theme_imgui_light()
dpg.bind_theme(theme)

width, height, channels, data = dpg.load_image("oscilloscope.jpg")

with dpg.texture_registry(show=False):
    dpg.add_static_texture(width=width, height=height, default_value=data, tag="bg_texture")

with dpg.window(label="USBTMC Configuration", tag="usbtmc_file_window", width=430, height=400, no_resize=True, no_close=True):
    dpg.add_input_text(label="USBTMC file", tag="usbtmc_file_input")
    
    with dpg.group(horizontal=True):
        dpg.add_button(label="Connect", callback=gui_rs232_connect)
        
    dpg.add_image("bg_texture")

    
with dpg.window(label="Oscilloscope commands", show=False, tag="oscilloscope_commands_window", pos=(400,0), no_close=True):
    dpg.add_button(label="Id", callback=lambda _: OscilloscopeId(ser))
    dpg.add_button(label="New immediate measurement", callback=lambda _: CreateMeasurementWindow())
    dpg.add_button(label="New curve acquisition", callback=lambda _: CreateCurveWindow())
    dpg.add_button(label="Events and errors log", callback=lambda _: OscilloscopeAlle(ser))


measurement_window_index = -1
def CreateMeasurementWindow():
    global measurement_window_index
    measurement_window_index = measurement_window_index + 1
    
    mw_index = measurement_window_index
    
    new_pos = [0,0]
    if mw_index != 0:
        new_pos = dpg.get_item_pos(f"measurement_window_{mw_index - 1}")
        new_pos[1] += 130
    
    with dpg.window(label=f"Measurement {mw_index}", show=True, tag=f"measurement_window_{mw_index}", height=130, width=250, pos=new_pos, no_resize=True, no_scrollbar=True):
        
        dpg.add_combo(items=[e.value for e in OscilloscopeChannel], label="Channel", tag=f"measurement_channel_combo_{mw_index}", default_value="CH1")
        dpg.add_combo(items=[e.value for e in OscilloscopeMeasurementType], label="Type", tag=f"measurement_type_combo_{mw_index}", default_value="PK2PK")
        
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_input_text(default_value="--", tag=f"measurement_text_{mw_index}", readonly=True)
            dpg.add_button(label="Measure", callback=lambda _: gui_immediate_measurement(mw_index))

        dpg.add_button(label="Copy to clipboard", callback=lambda _: pyperclip.copy(dpg.get_value(f"measurement_text_{mw_index}")))
            

curve_window_index = -1
def CreateCurveWindow():
    global curve_window_index
    curve_window_index = curve_window_index + 1
    
    cw_index = curve_window_index
    
    new_pos = [0,0]
    if cw_index != 0:
        new_pos = dpg.get_item_pos(f"curve_window_{cw_index - 1}")
        new_pos[1] += 400
        
        
    acquisitions.append([
            [[0], [0]],
            [[0], [0]]
        ])
    
    with dpg.window(label=f"Curve {cw_index}", show=True, tag=f"curve_window_{cw_index}", min_size=(550,400), pos=new_pos, no_resize=False, no_scrollbar=True):
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="Capture both", callback=lambda _: gui_curve_acquisition(cw_index, [OscilloscopeChannel.CH1, OscilloscopeChannel.CH2]))
            
            dpg.add_spacer()
            
            dpg.add_button(label="Capture CH1", callback=lambda _: gui_curve_acquisition(cw_index, [OscilloscopeChannel.CH1]))
            dpg.add_button(label="Capture CH2", callback=lambda _: gui_curve_acquisition(cw_index, [OscilloscopeChannel.CH2]))
            
        with dpg.group(horizontal=True):
            dpg.add_button(label="Export CSV", callback= lambda _: gui_save_curve_csv(cw_index))
            dpg.add_button(label="Export plot", callback= lambda _: gui_save_curve_plot(cw_index))
        
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_combo(items=[e.value for e in CurveType], default_value="OSCILLOSCOPE", tag=f"curve_type_combo_{cw_index}", callback=lambda _: gui_update_curve_plot(cw_index))

        
        with dpg.plot(label="Oscilloscope acquisition", height=-1, width=-1):
            dpg.add_plot_legend()

            dpg.add_plot_axis(dpg.mvXAxis, label="Time [s]", tag=f"x_curve_axis_{cw_index}")
            dpg.add_plot_axis(dpg.mvYAxis, label="Read", tag=f"y_curve_axis_{cw_index}")
            
            dpg.add_line_series([0], [0], parent=f"y_curve_axis_{cw_index}", tag=f"curve_series_1_{cw_index}", label="CH1")
            dpg.add_line_series([0], [0], parent=f"y_curve_axis_{cw_index}", tag=f"curve_series_2_{cw_index}", label="CH2")
            
    
            

with dpg.window(label="Communication log", show=False, tag="communication_log_window", no_close=True, min_size=(400, 240)):
    def toggle_auto_scroll(checkbox, checked):
        dpg.configure_item("communication_log_text", tracked=checked)
    
    dpg.add_checkbox(label="Autoscroll", default_value=True, callback=toggle_auto_scroll)
    
    with dpg.child_window():
        dpg.add_input_text(tag="communication_log_text", multiline=True, readonly=True, tracked=True, track_offset=1, width=-1, height=0)
    
with dpg.window(label="About", no_close=True, no_resize=True, pos=(0, 400)):
    dpg.add_text("Developed by Achille Merendino in 2024")
    dpg.add_button(label="Visit my homepage", callback=lambda: webbrowser.open("https://achilleme.com"))
    
    dpg.add_separator()
    
    dpg.add_text("Based on the following documents")
    dpg.add_button(label="TEK232 Documents", callback=lambda: webbrowser.open("https://achilleme.com/tek232"))
    

dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
