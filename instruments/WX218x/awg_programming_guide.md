4-1
Chapter 4
Programming Reference
Title Page
Chapter.......................................................................................................4-3
Introduction to SCPI ...........................................................................................................4-3
Command Format..........................................................................................................4-4
Command Separator .....................................................................................................4-4
The MIN and MAX Parameters .....................................................................................4-5
Querying Parameter Setting ..........................................................................................4-5
Query Response Format ...............................................................................................4-5
SCPI Command Terminator ..........................................................................................4-5
IEEE-STD-488.2 Common Commands.........................................................................4-5
SCPI Parameter Type ...................................................................................................4-6
Numeric Parameters ..................................................................................................4-6
Discrete Parameters ..................................................................................................4-6
Boolean Parameters ..................................................................................................4-6
Arbitrary Block Parameters ........................................................................................4-6
Binary Block Parameters ...........................................................................................4-6
SCPI Syntax and Styles .....................................................................................................4-7
WX2184C Commands .......................................................................................................4-7
Channel & Group Control Commands..............................................................................4-19
Run Mode Commands .....................................................................................................4-26
Analog Output Control Commands...................................................................................4-39
Marker Output Control Commands...................................................................................4-51
Standard Waveforms Control Commands ........................................................................4-56
Arbitrary Waveforms Control Commands .........................................................................4-61
Digital Output Control Commands....................................................................................4-73
Sequenced Waveforms Control Commands ....................................................................4-83
Advanced Sequencing Control Commands......................................................................4-92
Modulated Waveforms Global Control Commands...........................................................4-98
Modulation Control Commands......................................................................................4-101
AM Programming.......................................................................................................4-104
FM Programming .......................................................................................................4-105
WX2184C
User Manual
4-2
Sweep Modulation Programming ..............................................................................4-106
Chirp Modulation Programming.................................................................................4-109
FSK Modulation Programming ..................................................................................4-113
ASK Modulation Programming ..................................................................................4-115
Frequency Hopping Modulation Programming .........................................................4-117
Amplitude Hopping Modulation Programming ..........................................................4-120
PSK Modulation Programming ..................................................................................4-122
QAM Modulation Programming .................................................................................4-127
Pulse Waveform Programming ...................................................................................... 4-131
Pulse Pattern Programming ........................................................................................... 4-142
LAN System Configuration Commands.......................................................................... 4-153
LXI Configuration Commands ........................................................................................ 4-157
Store/Recall Commands ................................................................................................ 4-160
The Store/Recall Folder Structure.............................................................................4-163
The Store/Recall File Names ....................................................................................4-164
The Store/Recall File Structure .................................................................................4-166
Recall Setup3 Example .........................................................................................4-166
Store Setup1 Example...........................................................................................4-169
System Commands ....................................................................................................... 4-199
Error Messages .........................................................................................................4-200
LAN, USB and GPIB Programming Considerations ....................................................... 4-204
IEEE-STD-488.2 Common Commands and Queries ..................................................... 4-214
WX2184C
User Manual
4-4
Command Format The format used to show commands in this manual is shown below:
```
The command syntax shows most commands (and some
```
```
parameters) as a mixture of upper and lowercase letters. The
```
uppercase letters indicate the abbreviated spelling for the
command. For shorter program lines, send the abbreviated form.
For better program readability, use the long form.
For example, in the above syntax statement, FREQ and
FREQUENCY are both acceptable forms. Use upper or lowercase
letters. Therefore, FREQ, FREQUENCY, freq, and Freq are all
acceptable. Other forms such as FRE and FREQUEN will generate
an error.
The above syntax statement shows the frequency parameter
enclosed in triangular brackets. The brackets are not sent with the
```
command string. A value for the frequency parameter (such as
```
```
Some parameters are enclosed in square brackets ([ ]). The
```
brackets indicate that the parameter is optional and can be omitted.
The brackets are not sent with the command string.
Command
Separator
```
A colon ( : ) is used to separate a command keyword from a lower
```
level keyword as shown below:
```
A semicolon ( ; ) is used to separate commands within the same
```
subsystem, and can also minimize typing. For example, sending the
following command string:
is the same as sending the following three commands:
Use the colon and semicolon to link commands from different
subsystems. For example, in the following command string, an error
is generated if both the colon and the semicolon are not used.
WX2184C
User Manual
4-6
SCPI Parameter
Type
The SCPI language defines four different data formats to be used in
program messages and response messages: numeric, discrete,
Boolean, and arbitrary block.
Numeric Parameters Commands that require numeric parameters will accept all
commonly used decimal representations of numbers including
optional signs, decimal points, and scientific notation. Special
values for numeric parameters like MINimum and MAXimum are
also accepted.
```
Engineering units using numeric parameters (e.g., MHz or kHz) can
```
also be sent. If only specific numeric values are accepted, the
```
function generator will ignore values which are not allowed and will
```
generate an error message. The following command is an example
of a command that uses a numeric parameter:
Discrete Parameters Discrete parameters are used to program settings that have a
```
limited number of values (i.e., FIXed, USER and SEQuence). They
```
have short and long form command keywords. Upper and
lowercase letters can be mixed. Query responses always return the
short form in all uppercase letters. The following command uses
discrete parameters:
Boolean Parameters Boolean parameters represent a single binary condition that is
either true or false. The generator accepts "OFF" or "0" for a false
condition. The generator accepts "ON" or "1" for a true condition.
The instrument always returns "0" or "1" when a boolean setting is
queried. The following command uses a boolean parameter:
The same command can also be written as follows:
Arbitrary Block
Parameters
Arbitrary block parameters are used for loading waveforms into the
generator's memory. Depending on which option is installed, the
```
WX2184C can accept binary blocks up to 16 M bytes (32 M bytes
```
```
with option -1). The following command uses an arbitrary block
```
parameter that is loaded as binary data:
Binary Block
Parameters
Binary block parameters are used for loading segment and
sequence tables into the generator's memory. Information on the
binary block parameters is given later in this chapter.
WX2184C
User Manual
4-8
Table 4-1, Model WX2184C Commands List Summary
1. Channel and Group Control Commands
Keyword Parameter Form Default Notes
:FORMat
: DATA SEParate | COMMon SEParate Common will download
the waveform into both of
the memories, Arbitrary
and Digital
:ARBitrary
:RESolution 1P | 2P 1P 2P will duplicate any
arbitrary wave for sync
between Arb and Dig
frequency
:INSTrument
[:SELect] CH1 | CH2 | CH3 | CH4 | 1 | 2 | 3 | 4 CH1 Select channel for prog
:SKEW -100e-12 to 100e-12 0 Channels Skew in samepart
:COUPle Couple 1&2 with 3&4
```
:OFFSet 0 to ±(n-128) (n = waveform length) 0 Course offset adjustment
```
:SKEW -3e-9 to 3e-9 0 Fine skew adjustment
:STATe OFF | ON | 0 | 1 0
:XINStrument
:MODE MASTer | SLAVe | MSLave MAST System configuration
```
:OFFSet 0 to n (n = waveform length) 0 Multi-instrument offset
```
:SKEW -5e-9 to 5e-9 0
:STATe OFF | ON | 0 | 1 0
2. Run Mode Commands
:ABORt Unconditional abort
:ARM Applies to Event Input
[:SEQuence]
:ECL Sets ECL level
:LEVel -5 to +5 1.6
:SLOPe POSitive | NEGative POS
:TTL Sets TTL level
:ENABle Unconditional enable
:INITiate
:CONTinuous
:ENABle SELF | ARMed SELF
:SOURce BUS | EVENt EVEN Defines enable source
[:STATe] OFF | ON | 0 | 1 1
:GATE
[:STATe] OFF | ON | 0 | 1 0
:TRIGger Applies to trigger input
[:IMMediate] Same as *trg
[:SEQuence]
:COUNt 1 to 16,777,216 1 Counted bursts
WX2184C
User Manual
4-10
```
Table 4-1, Model WX2184C Commands List Summary (Continued)
```
Keyword Parameter Form Default Notes
:FUNCtion
:MODE FIXed | USER | SEQuence | ASEQuence | MODulation |
PULSe | PATTern
FIX Selects function type
:ROSCillator
:SOURce INTernal | EXTernal INT
[:EXTernal]
:FREQuency 10M | 20M | 50M | 100M 100M
:VOLTage DC coupled output
[:LEVel]
[:AMPLitude]
[:DC] 50e-3 to 2 | MINimum | MAXimum 500e-3 DC amplitude in volts
:ALL 50e-3 to 2 | MINimum | MAXimum 500e-3 Amplitude for all channels
:HV 50e-3 to 4 MINimum | MAXimum 500e-3 HV amplitude in volts
:ALL 50e-3 to 4 MINimum | MAXimum 500e-3 Amplitude for all channels
:OFFSet -1.0 to 1.0 | MINimum | MAXimum 0 DC offset in volts
:ALL -1.0 to 1.0 | MINimum | MAXimum 0 Offset for all channels
4. Marker Output Commands
[:SOURce]
:MARKer Selects active marker
:SELect 1 | 2 1
:STATe OFF | ON | 0 | 1 0 Toggles marker on/off
:DELay 0 to 3e-9 0 Delay from SYNC
```
:POSition 0 to n-2 (n = segment length) 0 Position from start
```
```
:WIDTh 2 to n (n = segment length) 4 Marker width
```
:SOURce WAVE | USER WAVE
:REFResh OFF | ON | 0 | 1 0 Toggles marker on/off
:VOLTage
[:LEVel]
:HIGH 0.5 to 1.2 0.5 Marker high level
5. Standard Waveforms Commands
[:SOURce]
:FUNCtion
:SHAPe SINusoid | TRIangle | SQUare | RAMP | SINC |
GAUSsian | EXPonential | NOISe | DC
SIN Standard function shape
:SINusoid
:PHASe 0 to 360.00 0
:TRIangle
:PHASe 0 to 360.00 0
:SQUare
:DCYCle 0 to 99.99 50
WX2184C
User Manual
4-12
```
Table 4-1, Model WX2184C Commands List Summary (Continued)
```
Keyword Parameter Form Default Notes
:HIGH -1.5 to 2 0.5
:LOW -2 to 1.5 0
:DELay -2.5e-9 to 2.5e-9 0
:MODe COMMon | SEParate COMM
:VOLTage
[:LEVel]
:HIGH -1.5 to 2 0.5
:LOW -2 to 1.5 0
:MODe COMMon | SEParate COMM Level mode
8. Sequenced Waveforms Commands
[:SOURce]
:SEQuence
:ADVance AUTOmatic | ONCE | STEPped AUTO
[:DATA] #<header><binary_block> Sequence data array
:DEFine <step>,<segment_#>,<loops>,<jump_flag> 3 step is minimum
:DELete
[:NAME] 1 to 1,000
:ALL
:JUMP
[:EVENt] BUS | EVENt BUS Toggle jump source
:LENGth 3 to 49,152 Optional definition
:SELect 1 to 1,000
:COUPle <1 to 1,000>,<1 to 1,000>
:SOURce BUS | EXTernal BUS Toggle control source
:TIMing COHerent | IMMediate COH Jump timing
:PREStep WAVE | DC WAVE DC is active in
continuous and BUS
source only
:ONCe
:COUNt 1 to 16,777,216
:SYNC
[:LOCK] <step_number> 1 Sync position
9. Advanced Sequencing Commands
[:SOURce]
:ASEQuence
:ADVance AUTOmatic | ONCE | STEPped AUTO
:DEFine <step>,<sequence_#>,<loops>,<jump_flag> 3 step is minimum
:DELete Deletes table
[:DATA] <data_array>
:LENGth 3 to 1,000 Optional definition
:ONCe
:COUNt 1 to 1,048,575
:SYNC
:LOCK 1 to 1,000 1 Sync position
WX2184C
User Manual
4-14
```
Table 4-1, Model WX2184C Commands List Summary (Continued)
```
Keyword Parameter Form Default Notes
:DEPTh 0 to 100% 50%
:DIRection UP | DOWN UP
:SPACing LINear | LOGarithmic LIN
:FSK
:FREQuency
:SHIFted 10e3 to 1000e6 10e6
:BAUD 0.1 to 500e6 10e3
:MARKer 1 to 256 1
:DATA <data_array>
:ASK
[:AMPLitude]
[:STARt] 0 to 2 2
:SHIFted 0 to 2 1
:BAUD 0.1 to 500e6 10e3
:MARKer 1 to 256 1
:DATA <data_array>
:FHOPping
:DWELl
:MODe FIXed | VARiable FIX
[:TIMe] 2e-9 to 10 5e-6
:FIXed
:DATA <data_array>
:VARiable
:DATA <data_array>
:MARKer 1 to 256 1
:AHOPping
:DWELl
:MODe FIXed | VARiable FIX
[:TIMe] 2e-9 to 10 5e-6
:FIXed
:DATA <data_array>
:VARiable
:DATA <data_array>
:MARKer 1 to 256 1
:PSK
:TYPE PSK | BPSK | QPSK | OQPSK | DQPSK | 8PSK | 16PSK
| USER
PSK
:PHASe
[:STARt] 0 to 360 0
:SHIFted 0 to 360 180
:DATA <data_array>
:MARKer 1 to 256 1
:BAUD 0.1 to 500e6 10e3
:CARRier
WX2184C
User Manual
4-16
```
Table 4-1, Model WX2184C Commands List Summary (Continued)
```
12.Pattern
Keyword Parameter Form Default Notes
:PATTern
:MODE COMPoser | PREDefined
[: PREDefined]
:TYPE PRBS7 | PRBS9 | PRBS11 | PRBS15 | PRBS23 |
PRBS31 | USER
PRBS7
:BAUD 1 to 500e6 10e6
:LEVel 2 | 3 | 4 | 5 2
:HIGH -2.0 to 2.0 1
:LOW -2.0 to 2.0 -1
:LOOPs 1 to 1e6 1
:PREamble 1 to 16e6 1
:LENGth 2 to 16e6 8
:DATA #<data_array>
:COMPoser
:TRANsition
:TYPe FAST | LINear FAST Transition type
:FAST
```
[:DATA] #<data_array> Level (float), Dwell
```
```
(Double)
```
:LINear
:STARt - 2 to +2 0.5
```
[:DATA] #<data_array> Level (float), Dwell
```
```
(Double)
```
:RESolution 500E-12 to 12.5e-9 <sec>
:TYPE AUTo | USER AUTo
13. LAN Configuration Commands
Keyword Parameter Form Default Notes
:SYSTem
:IP
[:ADDRess] <IP_address>
:MASK <mask>
:GATeway <gate_way>
:BOOTp OFF | ON | 0 | 1 0
```
HOSTname: <host_name>
```
:KEEPalive
:STATe OFF | ON | 0 | 1 1
:TIMEout 2 to 300 45
:PROBes 2 to 10 2
WX2184C
User Manual
4-18
```
Table 4-1, Model WX2184C Commands List Summary (Continued)
```
16. System Commands
Keyword Parameter Form Default Notes
:RESet
:SYSTem
:ERRor?
:LOCal Return to local
:TEMPerature?
:POWerup DEFault | SETup SET
:VERSion?
:INFormation
:CALibration?
:MODel?
:SERial?
:HARDware?
*CLS
*OPC
*RST
*TRG
*IDN?
*OPC?
```
*OPT? 4016, 4016D (16M) ; 4032, 4032D (32M) D, indicate that Digital
```
option is installed
*STB?
*TST?
WX2184C
User Manual
4-20
Table 4-2, Channel & Group Control Commands Summary
Keyword Parameter Form Default Notes
:FORMat
: DATA SEParate | COMMon SEParate Common will download
the waveform into both of
the memories, Arbitrary
and Digital
:ARBitrary
:RESolution 1P | 2P 1P 2P will duplicate any
arbitrary wave for sync
between Arb and Dig
frequency
:INSTrument
[:SELect] CH1 | CH2 | CH3 | CH4 | 1 | 2 | 3 | 4 CH1 Select channel for prog
:SKEW -100e-12 to 100e-12 0 Channels Skew in samepart
:COUPle Couple 1&2 with 3&4
```
:OFFSet 0 to ±(n-128) (n = waveform length) 0 Course offset adjustment
```
:SKEW -3e-9 to 3e-9 0 Fine skew adjustment
:STATe OFF | ON | 0 | 1 0
:XINStrument
:MODE MASTer | SLAVe | MSLave MAST System configuration
```
:OFFSet 0 to n (n = waveform length) 0 Multi-instrument offset
```
:SKEW -5e-9 to 5e-9 0
:STATe OFF | ON | 0 | 1 0
```
:FORMAT:DATA{SEParate|COMMon}(?)
```
Description
This command will set whether an arbitrary waveform is downloaded only to the arbitrary memory
or to both the arbitrary and digital memory
Parameters
Name Range Type Default Description
SEParate string SEParate SEP Sets the waveform download to the arbitrary memory
only.
COMMon string Sets the waveform download to both the arbitrary
memory and to the digital memory. This will provide
a digital representation of the analog waveform.
Response
The WX2184C will return SEP or COMM depending on the selected setting.
```
:FORMAT:ARBitrary:RESolution{1P|2P}(?)
```
Description
This command will set how the arbitrary waveform is written in the arbitrary memory.
WX2184C
User Manual
4-22
The two channels must have the same waveform
length in order for the phase skew parameter to be
meaningful. The skew range is programmable in
units of seconds throughout the range of 3 ns.
Coarse adjustment of phase offset between channels
is achieved using the inst:coup:offs command. Note
that this parameter is operating in conjunction with
the continuous run mode only..
Response
The WX2184C will return the present value of the skew setting in units of seconds.
```
:INSTrument:COUPle:OFFSet{<ch_offset>}(?)
```
Description
When couple state is ON, this command sets or queries the offset between the start phase of the master
```
channels (CH1 and CH2) and the start phase of the slave channels (CH3 and CH4). The inst:coupl:offset
```
command is applied automatically to channels 3 and 4 and does not require that you use the inst:sel 3
command.
Parameters
Name Range Type Default Description
<ch_offset> 0 to n-128 Numeric
```
(integer
```
```
only)
```
0 Defines a coarse phase offset between two pairs of
channels. Fine adjustment of phase offset between
channels is achieved using the inst:coup:skew
command. Note that this parameter is operating in
conjunction with the continuous run mode and only
when the two channel pairs are synchronized.
Response
The WX2184C will return the present value of the coarse offset setting in units of waveform points.
```
:INSTrument:COUPle:SKEW{<ch_skew>}(?)
```
Description
When couple state is ON, this command sets or queries the skew between two pairs of channels - channels
1/2 and channels 3/4. Skew defines fine offset between channels in units of time. The skew is computed for
channels 3 and 4 in reference to channels 1 and 2. The inst:coupl:skew command is applied automatically to
channels 3 and 4 and does not require that you use the inst:sel 3 command.
Parameters
Name Range Type Default Description
<ch_skew> -5e-9 to 5e-9 Numeric 0 Defines channels 3 and 4 skew in reference to
channels 1 and 2. Note that this parameter is
operating in conjunction with the continuous run
mode and only when all four channels are
synchronized.
WX2184C
User Manual
4-24
```
:XINStrument:OFFSet{<instrument_offset>}(?)
```
Description
When couple state is ON, this command sets or queries the offset between the start phase of the slave
instrument in reference to the master.
Parameters
Name Range Type Default Description
<instrumen
t_offset>
0 to n Numeric
```
(integer
```
```
only)
```
0 Defines a coarse phase offset between two
instruments. When offset is applied to one instrument
it is always in reference to the other instrument. For
example, offsetting the slave instrument by 1024
points and then offsetting master instrument by 2048
points will cause slave waveform to lag the master
waveform by 1024 points. Offset can be
programmed in increments of 8 sample clock
periods.
Response
```
The WX2184C will return the present value of the coarse offset setting in units of waveform points (SCLK
```
```
periods).
```
```
:XINSTrument: SKEW{<instrument_skew>}(?)
```
Description
When couple state is ON, this command sets or queries the skew between two instrument - master and
slave. Skew defines fine offset between instruments in units of time. The skew is computed for the slave
instrument in reference to the master.
Parameters
Name Range Type Default Description
<instrumen
t_skew>
-5e-9 to 5e-9 Numeric 0 Defines channels slave skew in reference to master.
Note that this parameter is operating in conjunction
with the continuous run mode and only when couple
state is on
Response
The WX2184C will return the present value of the skew setting in units of seconds.
```
:XINSTrument:STATe{OFF|ON|0|1}(?)
```
Description
Sets or queries the couple state of the synchronized instruments. Use this command to synchronize two
WX2184C
User Manual
4-26
Run Mode
Commands
The Run Mode Commands group is used to synchronize device
actions with external or internal events.
The WX2184C can operate in two basic modes: self-armed and
armed-for -enable.
Self-armed mode is the default option where waveforms are
generated at the output connector, immediately after the output
```
function has been selected.
```
In armed mode, the WX2184C requires an enable command or an
external analog event to cause the output to generate waveforms
and when already armed, a remote abort command will cease the
generation of the signal and the output will return to a known idle
state. This mode is very useful to control how and when the
waveform will start and stop for systems that require precise control
of waveform timing.
Other commands in this group control the basic run modes of the
waveform generator. The available run modes are:
continuous, where waveforms are generated continuously at
the output connector and triggered and gated.
conditional, where waveforms are generated on conditional
events, regardless if they are generated internally from a built-
in trigger generator or applied externally to the trigger and
event inputs.
Also use the commands in this group to control the sensitivity, the
polarity and other conditions of which external signals will affect the
trigger and event inputs.
A built-in counter is available to control a precise number of cycles
for applications requiring a burst of waveforms that follows a trigger
event.
Additional information on the run mode options and how the
generator behaves under the various run mode options is given in
Chapter 3. Factory defaults after *RST are shown in the default
column. Parameter low and high limits are given where applicable.
Use the commands in Table 4-3 to set up the WX2184C run mode
and for setting up the input conditions for the various trigger inputs.
WX2184C
User Manual
4-28
:ABORt
Description
Use this command for an immediate and unconditional termination of the output waveform. A prerequisite
condition that makes this command effective is to place the WX2184C in continuous and armed run mode
and then enable the output using the enab command. This command is also effective in all triggered run
mode options. Following the abort command, the WX2184C stops generating waveforms and the output
starts generating an idle waveform that could be one of: dc, first waveform in a sequence or first sequence
in an advanced sequence scheme. The abort command ignores the trac:sel:tim and the sequ:sel:tim
settings. The resulting scenarios of the abort command are summarized in the Run Modes Summary table
in Chapter 3.
:ARM:ECL
Description
```
Use this command to set the event input to accept ecl (negative) signals. The threshold level is
```
automatically set to -1.3 V, which is the mid-level for negative ecl logic. Other related commands are: arm:ttl
to set the threshold level for TTL signals and arm:lev to program a threshold level between -5 V to 5 V. Note
that commands that start with ARM affect the conditions for the event input only.
```
:ARM:LEVel<level>(?)
```
Description
This command programs the threshold level for the event input signals. Other related commands are:
```
arm:ttl to set the threshold level for TTL signals and arm:ecl to program a threshold level for ECL signals.
```
Note that commands that start with ARM affect the conditions for the event input only.
Parameters
Name Range Type Default Description
<level> -5 to 5 Numeric 1.6 Programs the threshold level for the invent input.
Response
The WX2184C will return the present threshold level setting in units of volts.
```
:ARM:SLOPe{POSitive|NEGative|EITHer}(?)
```
Description
Use this command to define the edge that will affect the event input. Positive going transitions will affect the
event input when the POS option is selected. Negative transitions will affect the event input when the NEG
option is selected. Both transitions will affect the event input when the EITH option is selected. Note that
commands that start with ARM affect the conditions for the event input only.
WX2184C
User Manual
4-30
Response
The WX2184C will return SELF, or ARM depending on the current enable mode setting.
```
:INITiate:CONTinuous{1|0|ON|OFF}(?)
```
Use this command to set or query the gated run mode status.
Parameters
Range Type Default Description
1-0 Discrete 1
continuous operation and forces the triggered run
mode. Trigger signal is applied to the trigger input
only and output waveforms will be generated only
when the trigger signal is valid and true. The slope
and level of the trigger input are programmable.
Response
The WX2184C will return 1 or 0 depending on the current run mode setting.
```
:INITiate:CONTinuous:ENABle:SOURce{BUS|EVENt }(?)
```
Description
Use this command to set or query the source of the enable signal. This command is effective in continuous
```
mode only and has no effect when the init:cont 0 or init:gate 1 (triggered or gated modes) were executed.
```
Parameters
Name Type Default Description
BUS Discrete BUS Defines the source of the enable signal as a remote
command sent over one of the interfacing controllers
```
(USB, LAN or GPIB). Signals at the event input will
```
be ignored. In continuous run mode, waveforms are
generated at the output connector as soon as a
remote enable command is executed. For an
immediate and unconditional termination of the output
waveform use the abor command.
EVENt Discrete Defines the source of the enable signal as the event
input connector. Remote enable commands will be
ignored. In continuous run mode, waveforms are
generated at the output connector as soon as a valid
event signal is sensed at the event input connector.
For an immediate and unconditional termination of
the output waveform use the abor command.
Response
The WX2184C will return BUS or EVEN depending on the current enable source setting.
WX2184C
User Manual
4-32
programmed to operate in triggered run mode. Modify the WX2184C to triggered run mode using the
```
init:cont 0 command. The delay interval is programmed in sample clock period increments.
```
Parameters
Name Range Type Default Description
<interval> 0 to 8e6 Numeric
```
(integer only)
```
0
programmed in sample clock period increments, so
expect the delay time to change if you modify your
sample clock setting. Program the delay interval
using integer numbers divisible by 8 only.
Response
The WX2184C will return the present trigger delay interval value.
:TRIGger:ECL
Description
```
Use this command to set the trigger input to accept ecl (negative) signals. The threshold level is
```
automatically set to -1.3 V, which is the mid-level for negative ecl logic. Other related commands are: trig:ttl
to set the threshold level for TTL signals and trig:lev to program a threshold level between -5 V to 5 V.
```
:TRIGger:FILTer:HPASs:WIDTh<width>(?)
```
Description
Use this command to set or query the trigger high pass filter value. Trigger signal having pulse width below
the programmed settings will not trigger the generator. The trigger filter has three options: high pass filter,
which will trigger the WX2184C only if the width is larger than the programmed value, low pass filter, which
will trigger the generator only if the width is smaller than the programmed value, and window pass filter,
which will trigger the generator only if the width is within a certain range specified by the high and low pass
filters.
The trig:fil:hpas:wid command sets a high pass threshold for the trigger signal and the trig:fil:lpas:wid
command sets a low pass threshold for the trigger signal. If both the high and low pass filters are turned on,
signals having a pulse width smaller than the low pass setting and larger that the high pass setting will
trigger the generator.
Parameters
Name Range Type Default Description
<time> 10e-9 to 2 Numeric 100e-3 Programs the high pass pulse width value in seconds
Response
The WX2184C will return the present high pass value in units of seconds.
WX2184C
User Manual
4-34
```
:TRIGger:HOLDoff<holdoff>(?)
```
Description
Use this command to set or query the trigger holdoff period. The trigger holdoff filter defines a period that
starts with the first valid trigger input and ends with the holdoff setting of which all triggers within this range,
valid or not, are ignored, but the first valid signal after the holdoff range will cause the WX2184C to
generate a waveform.
Parameters
Name Range Type Default Description
<time> 0.1e-9 to 2 Numeric 10e-9 Programs the trigger holdoff period in units of second.
Response
The WX2184C will return the present holdoff value in units of second.
```
:TRIGger:HOLDoff:STATe{OFF|ON|0|1}(?)
```
Description
Use this command to set or query the status of the holdoff filter.
Range Type Default Description
0-1 Discrete 0 Turns the holdoff filter on and off.
Response
The WX2184C will return 0 or 1 depending on the present holdoff filter state.
```
:TRIGger:LEVel<level>(?)
```
Description
Use this command to program or query the threshold level for the trigger input signals. Other related
commands are: trig:ttl to set the threshold level for TTL signals and trig:ecl to program a threshold level for
ECL signals. Note that commands that start with trig affect the conditions for the trigger input only.
Parameters
Name Range Type Default Description
<level> -5 to 5 Numeric 1.6 Programs the threshold level for the trigger input.
Response
The WX2184C will return the present threshold level setting in units of volts.
WX2184C
User Manual
4-36
```
:TRIGger:SOURce:ADVance{EXTernal|BUS|TIMer|EVENt}(?)
```
Description
Use this command to set or query the source of the trigger event that will stimulate the WX2184C to
generate waveforms. The source advance command will affect the generator only after it has been
programmed to operate in trigger run mode. Modify the WX2184C to trigger run mode using the init:cont off
command.
Parameters
Name Type Default Description
EXTernal Discrete EXT Selects the TRIG IN connector as the input source.
The front panel MANUALcan be used in case
external triggers are not available. All other inputs are
ignored.
BUS Discrete Selects the remote controller as the trigger source.
```
Only software commands are accepted; TRIG IN,
```
Event IN and manual triggers are ignored.
TIMer Discrete Activates the built in internal trigger generator. BUS
and external trigger are ignored. The period of the
internal trigger is programmable and can be used to
replace an external trigger source.
EVENt Discrete Selects the Event IN connector as the input source.
All other inputs are ignored.
Response
The WX2184C will return EXT, BUS, TIM, or EVEN depending on the selected trigger source advance
setting.
WX2184C
User Manual
4-38
generator is a free-running oscillator, asynchronous with the frequency of the output waveform. The timer
intervals are measured from waveform start to waveform start.
Parameters
Name Range Type Default Description
<timer> 200e-9 to 20 Numeric 15e-6 Programs the internal timed trigger generator period
in units of seconds.
Response
The WX2184C will return the present internal timed trigger period value in units of seconds.
:TRIGger:TTL
Description
Use this command to set the trigger input to accept ttl signals. The threshold level is automatically set to 1.6
V, which is the mid-level for ttl logic. Other related commands are: trig:ecl to set the threshold level for ECL
signals and trig:lev to program a threshold level between -5 V to 5 V.
WX2184C
User Manual
4-40
```
Table 4-4, Analog Output Commands Summary (Continued)
```
[:EXTernal]
:FREQuency 75e6 to 2.3e9 | MINimum | MAXimum 1e9
:FUNCtion
:MODE FIXed | USER | SEQuence | ASEQuence | MODulation |
PULSe | PATTern
FIX Selects function type
:ROSCillator
:SOURce INTernal | EXTernal INT
[:EXTernal]
:FREQuency 10M | 20M | 50M | 100M 100M
:VOLTage DC coupled output
[:LEVel]
[:AMPLitude]
[:DC] 50e-3 to 2 | MINimum | MAXimum 500e-3 DC amplitude in volts
:ALL 50e-3 to 2 | MINimum | MAXimum 500e-3 Amplitude for all channels
:HV 50e-3 to 4 MINimum | MAXimum 500e-3 HV amplitude in volts
:ALL 50e-3 to 4 MINimum | MAXimum 500e-3 Amplitude for all channels
:OFFSet -1.0 to 1.0 | MINimum | MAXimum 0 DC offset in volts
:ALL -1.0 to 1.0 | MINimum | MAXimum 0 Offset for all channels
```
:OUTPut:COUPling{DC|HV}(?)
```
Description
Use this command to set or query the type of output amplifier that will be placed between the DAC and the
output connectors.
Parameters
Name Type Default Description
DC Discrete Selects a DC-coupled amplifier path for the output
amplifier. Use the volt and volt:offs commands to
control output amplitude and offset.
HV Discrete Selects a high voltage DC-coupled amplifier path for
the output amplifier. Use the volt and volt:offs
commands to control output amplitude and offset.
Response
The WX2184C will return DC or HV depending on the current output coupling setting.
```
:OUTPut:COUP:ALL{DC|HV}
```
Description
Use this command to set the type of output amplifier that will be placed between the DAC and the output
connectors for ALL channels.
WX2184C
User Manual
4-42
```
:OUTPut:SYNC:FUNCtion{PULSe|WCOMPlete}(?)
```
Description
Use this command to set or query the shape of the sync pulse. Pulse output can be programmed for
```
position and width and the WCOM (wave complete) as fixed and cannot be moved from its origin.
```
Parameters
Name Type Default Description
PULSe Discrete PULS Selects the pulse shape as the output waveform for
the sync output. The minimum pulse width is 32
sample clock periods. However, the width can be
expanded to the full length of the waveform in
increments of 32 points. Program the sync pulse
width using the outp:sync:wid command and its
relative position to the start of the waveform using the
```
outp:sync:pos command.
```
WCOMplete Discrete This will select the waveform complete pulse option.
The sync output will transition high at the beginning of
the waveform and will return to low after the
waveform cycle has been completed. Width and
position control of the sync pulse is not available
when this option is selected.
Response
The WX2184C will return PULS or WCOM, depending on the selected SYNC waveform function.
```
:OUTPut:SYNC:POSition<position>(?)
```
Description
```
This command will program the WX2184C SYNC position. This command is active in arbitrary (USER)
```
mode only.
Parameters
Name Range Type Default Description
<position> 0 to n Numeric
```
(Integer
```
```
only)
```
0 Will set the SYNC position in waveform points. The
sync position can be programmed in increments of 32
points to the maximum length of the waveform
providing that the number is divisible by 32.
Response
The WX2184C will return the present SYNC position value.
WX2184C
User Manual
4-44
Parameters
Name Range Type Default Description
<freq> 10e-3 to 1e9 Numeric 10e6 Will set the frequency of the standard waveform in
units of Hz. The frequency command can be used
with resolutions up to 8 digits.
<MINimum> Discrete Will set the frequency of the standard waveform to
```
the lowest possible frequency (10e3).
```
<MAXimum> Discrete Will set the frequency of the standard waveform to
```
the highest possible frequency (1e9).
```
Response
The WX2184C will return the present frequency value. The returned value will be in standard scientific
```
format (for example: 100mHz would be returned as 100e-3 positive numbers are unsigned).
```
```
:FREQuency:RASTer{<sclk>|MINimum|MAXimum}(?)
```
Description
Use this command to set or query the sample clock frequency of the arbitrary waveform in units of samples per
```
second (Sa/s). This parameter has no effect on standard waveforms.
```
Parameters
Name Range Type Default Description
<sclk> 10e6 to 2.3e9 Numeric 1e9 Will set the sample clock frequency of the arbitrary
and sequenced waveform in units of Sa/s. The
sample clock command can be programmed with
resolutions up to 8 digits.
<MINimum> Discrete Will set the sample clock frequency to the lowest
```
possible frequency (10e6).
```
<MAXimum> Discrete Will set the frequency of the standard waveform to
```
the highest possible frequency (2.3e9).
```
Response
The WX2184C will return the present sample clock frequency value. The returned value will be in standard
```
scientific format (for example: 1 GHz would be returned as 1e9 positive numbers are unsigned).
```
:FREQuency:RASTer:FIX?
Description
Query only. Use this command to query the sample clock frequency which is generated internally to clock the
standard waveform shape..
Response
The WX2184C will return the present sample clock frequency value. The returned value will be in standard
```
scientific format (for example: 1 GHz would be returned as 1e9 positive numbers are unsigned).
```
WX2184C
User Manual
4-46
ASEQuenced Discrete Selects the advanced sequencing waveform output. To
generate an advanced sequences, you must first
download waveform coordinates to different segments,
use these waveforms to design sequences and then use
these sequences to build an advanced sequence table
where sequences are sequenced to create an extremely
complex waveform.
MODulated Discrete Selects the modulated waveforms. There is an array of
built-in modulation schemes. However, you can also build
custom modulation schemes using the arbitrary function.
PULSe Discrete Selects the digital pulse function. The digital pulse function
behaves and reacts to the programming sequence as a
regular pulse generator, except the waveforms are
digitally constructed and generated from the arbitrary
memory.
PATTern Discrete Selects the pulse pattern function. The pulse pattern
```
function behaves and reacts to the programming
```
sequence as a regular pattern generator, except the
waveforms are digitally constructed and generated from
the arbitrary memory.
Response
The WX2184C will return FIX, USER, SEQ, ASEQ, MOD, PULS, or PATT depending on the present
output function mode setting.
```
:ROSCillator:SOURce{INTernal|EXTernal}(?)
```
Description
Use this command to set or query the source of the 10 MHz reference. This source defines the accuracy
```
and stability of the clock generator. The internal reference has an accuracy and stability of 1 ppm;
```
applications requiring higher accuracy or stability can use the external reference input.
Parameters
Name Type Default Description
INTernal Discrete INT Selects an internal source. The internal source is a
```
TCXO (temperature compensated crystal oscillator)
```
device that has 1ppm accuracy and stability over the
operating temperature range.
EXTernal Discrete Replaces the internal reference clock with the signal
which is applied to the external reference input. An
external reference signal must be connected to the
WX2184C for it to continue with its normal operation.
Response
The WX2184C will return INT, or EXT depending on the present clock reference source setting.
WX2184C
User Manual
4-48
Parameters
Name Range Type Default Description
<dc_voltage> 50e-3 to 2 Numeric 500e-3 Will set the amplitude of the output waveform in units
of volts. The display shows the correct amplitude level
only when the output cable is terminated into 50 .
```
<MINimum> Discrete Will set the amplitude to the lowest possible level (50e-
```
```
3).
```
```
MAXimum> Discrete Will set the amplitude to the highest possible level (2).
```
Response
The WX2184C will return the present dc amplitude value. The returned value will be in standard scientific
```
format (for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
```
:VOLTage:HV{<hv_voltage>|MINimum|MAXimum}(?)
```
Description
Use this command to set or query the amplitude of the waveform when routed through the HV path. This
parameter affects the HV output paths only. Use the command outp:coup hv to modify the output path to
hv-coupled. The WX2184C displays a calibrated value when on load impedance of 50 . Offset and
amplitude settings are independent providing that the |offset + amplitude/2| value does not exceed the
specified voltage window.
Parameters
Name Range Type Default Description
<dc_voltage> 50e-3 to 4 Numeric 500e-3 Will set the amplitude of the output waveform in units of
volts. The display shows the correct amplitude level
only when the output cable is terminated into 50 .
```
<MINimum> Discrete Will set the amplitude to the lowest possible level (50e-
```
```
3).
```
```
MAXimum> Discrete Will set the amplitude to the highest possible level (4).
```
Response
The WX2184C will return the present HV amplitude value. The returned value will be in standard scientific
```
format (for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
```
:VOLTage:HV:ALL{<hv_voltage>|MINimum|MAXimum}(?)
```
Description
Use this command to set the amplitude of the waveform for ALL channels when routed through the HV
path. This parameter affects the HV output paths only. Use the command outp:coup:all hv to modify the
output path to hv-coupled. The WX2184C displays a calibrated value when on load impedance of 50 .
Offset and amplitude settings are independent providing that the |offset + amplitude/2| value does not
exceed the specified voltage window.
WX2184C
User Manual
4-50
```
<MINimum> Discrete Will set the offset to the lowest possible level (-1.0).
```
```
<MAXimum> Discrete Will set the offset to the highest possible level (1.0).
```
Response
The WX2184C will return the present dc offset value. The returned value will be in standard scientific format
```
(for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
WX2184C
User Manual
4-52
Table 4-5, Marker Output Control Commands Summary
4. Marker Output Commands
Keyword Parameter Form Default Notes
[:SOURce]
:MARKer Selects active marker
:SELect 1 | 2 1
:STATe OFF | ON | 0 | 1 0 Toggles marker on/off
:DELay 0 to 3e-9 0 Delay from SYNC
```
:POSition 0 to n-4 (n = segment length) 0 Position from start
```
```
:WIDTh 0 to n-4 (n = segment length) 4 Marker width
```
:SOURce WAVE | USER WAVE
:VOLTage
[:LEVel]
:HIGH 0.5 to 1.2 0.5 Marker high level
```
:MARKer:SELect{1|2|}(?)
```
Description
This command will select the active marker for future programming command sequences. Subsequent
commands affect the selected marker only.
Parameters
Range Type Default Description
1-2 Discrete Sets the active marker for programming from remote.
Response
The WX2184C will return 1 or 2 depending on the present active marker setting.
```
:MARKer:DELay<delay>(?)
```
Description
Use this command to set or query the delay of the marker output. The delay is measured from the sync
output in units of seconds. The marker has an initial width of 4 sample clock periods and an amplitude
swing of 0 to 0.5 V. Use the mark:wid command to change the marker pulse width.
Parameters
Name Range Type Default Description
<delay> 0 to 3e-9 Numeric 0 Will set marker delay value in units of seconds. Each
channel has two separate markers that can be
programmed to have unique delays and amplitude
levels. Note that you can program D14 and D15 to
create multiple markers along the waveform length
however, in this case, you must remove the default
marker from the waveform map by setting the width
parameter mark:wid 0.
WX2184C
User Manual
4-54
```
:MARKer:WIDth<width>(?)
```
Description
Use this command to set or query the width of the marker output. The width is defined in units of
```
waveform points (sample clock periods). The marker has an initial amplitude swing of 0 to 0.5 V. Use the
```
command mark[1|2]:volt:high|low to change the marker amplitude levels.
Parameters
Name Range Type Default Description
<width> 2 to n Numeric 4 Will set marker width in units of waveform points. The
width range is from 0 to the last point of the waveform less
4. You can program the width in increments of 2 points.
Note that you can program D14 and D15 to create multiple
markers along the waveform length however, in this case,
you must remove the default marker from the waveform
map by setting the width parameter mark:wid 0.
Response
The WX2184C will return the present marker width value in units of waveform points.
```
:MARKer:VOLTage:HIGH<hi_level>(?)
```
Description
Use this command to set or query the high level of the marker output. The high level is defined in units of
volts.
Parameters
Name Range Type Default Description
<hi_level> 0.5 to 1.2 Numeric 0.5 Will program the marker high level in units of volts.
Each marker can be programmed to a different low-
and high-level setting. The high level is calibrated
when the cable is terminated into a 50 load.
Response
The WX2184C will return the present marker high-level value. The returned value will be in standard
```
scientific format (for example: 0.51 V would be returned as 510e-3 positive numbers are unsigned).
```
WX2184C
User Manual
4-56
Standard
Waveforms
Control
Commands
Use this group to control the shape and parameters of the standard
waveforms functions. The commands in this group will affect the
output only when the WX2184C has been programmed to generate
standard waveforms. In standard waveform mode, some waveform
coordinates are stored in tables and some are computed every time
a waveform is being selected or modified. Expect small delays after
the commands have been sent, because the waveform is
recomputed and refreshed with every command.
Factory defaults after *RST are shown in the Default column.
Parameter range and low and high limits are listed, where
applicable. Use the commands in Table 4-6 to set up the WX2184C
standard waveforms and their associated parameters.
Table 4-6, Standard Waveforms Control Commands Summary
Keyword Parameter Form Default Notes
[:SOURce]
:FUNCtion
:SHAPe SINusoid | TRIangle | SQUare | RAMP | SINC |
GAUSsian | EXPonential | NOISe | DC
SIN Standard function shape
:SINusoid
:PHASe 0 to 360.00 0
:TRIangle
:PHASe 0 to 360.00 0
:SQUare
:DCYCle 0 to 99.99 50
:RAMP
:DELay 0 to 99.99 10
:TRANsition
[:LEADing] 0 to 99.99 60
:TRAiling 0 to 99.99 30
:SINC
:NCYCle 4 to 100 10
:GAUSsian
:EXPonent 1 to 200 10
:EXPonential
:EXPonent -100 to 100 -10
:DC
[:OFFSet] -1 to 1 0 DC coupled only
WX2184C
User Manual
4-58
```
:TRIangle:PHASe<phase>(?)
```
Description
Use this command to set or query the start phase for the standard triangular waveform.
Parameters
Name Range Type Default Description
<phase> 0 to 360 Numeric 0 Programs the start phase parameter in units of
degrees. Triangle phase resolution is 0.01 limited
however at high frequencies, depending on the
number of waveform points that are used to create
the shape.
Response
The WX2184C will return the present start phase value in units of degrees.
```
:SQUare:DCYCle<duty_cycle>(?)
```
Description
Use this command to set or query the duty cycle of the standard square waveform.
Parameters
Name Range Type Default Description
<duty_cycle> 0 to 99.99 Numeric 50 Programs the duty cycle of the standard square
waveform in units of percent. Duty cycle setting
resolution is limited to 0.01% of the square wave
period.
Response
The WX2184C will return the present duty cycle value in units of percent.
```
:RAMP:DELay<delay>(?)
```
Description
Use this command to set or query the delay of the standard ramp waveform. The delay parameter defines
the time that will lapse from the waveform start to the first transition of the ramp period.
Parameters
Name Range Type Default Description
<delay> 0 to 99.99 Numeric 10 Programs the ramp delay parameter in units of
percent
Response
The WX2184C will return the present ramp delay value in units of percent.
WX2184C
User Manual
4-60
```
:GAUSsian:EXPonent<exp>(?)
```
Description
Use this command to set or query the exponent for the standard Gaussian pulse waveform.
Parameters
Name Range Type Default Description
<exp> 1 to 200 Numeric
```
(Integer only)
```
10 Programs the exponent parameter.
Response
The WX2184C will return an integer number depending on the present exponent value.
```
:EXPonential:EXPonent<exp>(?)
```
Description
Use this command to set or query the exponent for the standard exponential pulse waveform.
Parameters
Name Range Type Default Description
<exp> -100 to 100 Numeric
```
(Integer only)
```
-10 Programs the exponent parameter.
Response
The WX2184C will return an integer number, depending on the present exponent value.
```
:DC<offset>(?)
```
Description
Use this command to set or query the offset of the DC function in units of volts.
Parameters
Name Range Type Default Description
<offset> -1 to 1 Numeric 0 Programs the DC offset parameter in units of volts.
Output amplifier path is automatically set to DC.
Response
The WX2184C will return the present DC offset value in units of volts.
WX2184C
User Manual
4-62
Table 4-7, Arbitrary Waveforms Commands Summary
Keyword Parameter Form Default Notes
:TRACe
:MODE SINGle | DUPLicate | ZERoed | COMBined DUPLicate Select waveform
download mode.
[:DATA] #<header><binary_block> Waveform data array
```
:DEFine <1 to 32,000>,<192 to 16(32)e6> Segment and length
```
:DEFine<n>? <n = 1 to 32,000> Query length of seg <n>
:DELete
[:NAME] 1 to 32,000 Delete one segment
:ALL Delete all segments
:POINts? Queries waveform length
:SELect 1 to 32,000 1
:COUPle <1 to 32,000>,<1 to 32,000>
:SOURce BUS | EXTernal BUS Toggle control source
:TIMing COHerent | IMMediate COH Select timing
:SEGment
[:DATA] #<header><binary_block> Segment data array
```
:TRACe:MODE{ SINGle | DUPLicate | ZERoed | COMBined }(?)
```
Description
This command will define how the arbitrary waveform is downloaded to the unit memory. The output
channels of the unit are arranged in pairs, meaning that each two channels share a single memory block of
```
32Mpoints (64Mpoints optional). The channel pair memory block is divided in such a way that the individual
```
```
channel s memory blocks (16Mpoints per channel in standard configuration) are interleaved in blocks of 16
```
points as depicted in Figure 4-1. Note, that the first 16 point data block is of Channel 2.
Figure 4-1, Channel pair memory block
WX2184C
User Manual
4-64
The generator accepts waveform samples as 16-bit integers, which are sent in two-byte words. Therefore,
the total number of bytes is always twice the number of data points in the waveform. For example, 20000
bytes are required to download a waveform with 10,000 points. The IEEE-STD-488.2 definition of Definite
Length Arbitrary Block Data format is demonstrated in Figure 4-2.
```
"#" non-zeroASCII digit ASCII digit low byte(binary) (binary)high byte
```
Start of
Data Block
Number of
to Follow
Byte Count:
2 x Number of
2 Byts Per
Data Point
Figure 4-2, Definite Length Arbitrary Block Data Format
Transfer of definite length arbitrary block data must terminate with the EOI bit set. This way, carriage-return
```
(CR 0dH) and line feed (LF 0aH) characters can be used as waveform data points and will not cause
```
unexpected termination of the arbitrary block data.
<binary_block> Represents waveform data.
```
The waveform data is made of 16-bit words however; programmers may choose to prepare the data in two
```
bytes and arrange to download these two bytes in a sequence. Figure 4-3 shows a waveform word that is
acceptable for the WX2184C. There are a number of points you should be aware of before you start
preparing the data:
1. Waveform data points have 14-bit values - 0x000 to 3xFFF.
2. Data point range is 0 to 16,383 decimal for the WX2184C. 0x000 corresponds to -2 V and 3xFFF
corresponds to +2 V.
3. WX2184C data point 16,383 corresponds to full-scale amplitude setting. Point 8,192 corresponds to 0V
amplitude setting.
4. The description above is relevant for download modes SINGle, DUPLicate and ZERoed. For
COMBined download mode refer to the next step.
5. In COMBined mode the data is written to both channels in each channel pair. It is written in blocks of
```
16 points alternating between the two channels (refer to TRACe:MODE command description). As an
```
example, the following command will download an arbitrary block of data of 2048 points, 1024 to each
channel of the channel pair.
Notice that the data must be prepared in the appropriate interleaved manner, 16point for each channel
beginning with CH2.
WX2184C
User Manual
4-66
by 12 points. Use the following programming example to position the markers:
```
Conditions:
```
1. mark_pos%2 = 0; mark_width%2 = 0;
2. mark_pos+mark_width < wave_length
```
Calculations:
```
```
marker_points = mark_width/2;
```
```
if(mark_pos+12>wave_length)
```
```
mark_pos=12-(wave_length-mark_pos)
```
else
```
mark_pos = mark_pos+12;
```
```
for(ii=0; ii<marker_points; ii++)
```
```
{
```
```
wave_index = 8*((integer)(mark_pos/16) + 1) + mark_pos/2;
```
```
mark_pos = mark_pos+2;
```
```
}
```
4.
Parameters
Name Type Description
<header> Discrete Contains information on the size of the binary block
that contains waveform coordinates.
<binary_block> Binary Block of binary data that contains waveform data
```
points (vertical coordinates), as explained above.
```
:TRACe:DEFine<segment_#>,<length>
Description
Use this command to define the size of a specific memory segment. The final size of the arbitrary memory
```
is 16,000,000 points (32,000,000 points optional). The memory can be partitioned to smaller segments, up
```
to 16,000 segments. The total length of memory segments cannot exceed the size of the waveform
memory.
NOTE
The WX2184C operates in interlaced mode where thirty-two memory cells generate
one byte of data. Therefore, segment size can be programmed in numbers evenly
divisible by 16 only. For example, 2112 bytes is an acceptable length for a binary
block. 2110 is not a multiple of 16 and therefore the generator will generate an error
WX2184C
User Manual
4-68
The WX2184C will return the active waveform length as an integer number.
```
:TRACe:SELect<segment_#>(?)
```
Description
Use this command to set or query the active waveform segment at the output connector. By selecting the
active segment, you are performing two functions:
1. Successive: TRAC commands will affect the selected segment.
2. The SYNC output will be assigned to the selected segment. This behavior is especially important for
sequence operation, where multiple segments form a large sequence. In this case, you can
synchronize external devices exactly to the segment of interest.
Parameters
Name Range Type Default Description
<segment_#> 1 to 32k Numeric
```
(Integer only)
```
1 Selects the active segment number.
Response
The WX2184C will return the active waveform segment number.
:TRACe:SELect:COUPle<seg_#>,<seg_#>
Description
This command is useful when the WX2184C is placed in coupled mode where all channels share the same
sample clock. Use this command to set or query the active waveform segment at all output connectors
simultaneously. Note that this command selects one segment from a table list that is associated with
channel 1 and 2 and another segment that is associated with channel 3 and 4. Also note that channels 1
and 2 always share the same segment number and so do channels 3 and 4.
By selecting the active segment, you are performing two functions:
1. Successive: TRAC commands will affect the selected segment.
2. The SYNC output will be assigned to the selected segment. This behavior is especially important
for sequence operation, where multiple segments form a large sequence. In this case, you can
synchronize external devices exactly to the segment of interest.
Parameters
Name Range Type Default Description
<seg_#> 1 to 32k Numeric
```
(Integer only)
```
1,1 Selects the active segment number simultaneously
for channels 1/2 and 3/4.
Response
The WX2184C will return the active waveform segment numbers.
WX2184C
User Manual
4-70
The WX2184C will return COH, or IMM depending on the present segment jump timing setting.
:SEGMent#<header><binary_block>
Description
This command will partition the waveform memory to smaller segments hence speeding up memory
segmentation. The idea is that waveform segments can be built as one long waveform and then just use this
command to split the memory to the appropriate memory segments. In this way, there is no need to define
and download waveforms to individual segments.
Using this command, segment table data is loaded to the WX2184C using high-speed binary transfer in a
similar way to downloading waveform data with the trace command. High-speed binary transfer allows any
```
8-bit bytes (including extended ASCII code) to be transmitted in a message. This command is particularly
```
useful for large number of segment. As an example, the next command will generate three segments with 12
bytes of data that contains segment size information.
SEGMent#212<binary_block>
```
This command causes the transfer of 12 bytes of data (3 segments) into the segment table buffer. The
```
<header> is interpreted this way:
```
The ASCII "#" ($23) designates the start of the binary data block.
```
"2" designates the number of digits that follow.
"12" is the number of bytes to follow. This number must divide by 4.
The generator accepts binary data as 32-bit integers, which are sent in two-byte words. Therefore, the total
number of bytes is always 4 times the number of segments. For example, 36 bytes are required to download
9 segments to the segment table. The IEEE-STD-488.2 definition of Definite Length Arbitrary Block Data
format is demonstrated in Figure 4-2. The transfer of definite length arbitrary block data must terminate with
```
the EOI bit set. This way, carriage-return (CR 0dH) and line feed (LF 0aH) characters can be used as
```
segment table data points and will not cause unexpected termination of the arbitrary block data.
The segment table data is made of 32-bit words however, the GPIB link has 8 data bus lines and accepts 8-
bit words only. Therefore, the data has to be prepared as 32-bit words and rearranged as six 8-bit words
before it can be used by the WX2184C as segment table data. Figure 4-5 shows how to prepare the 32-bit
word for the segment start address and size. Actually, only size is required because the segments are
automatically numbered and their relative start address is automatically placed at the end of the last memory
segment.
There are a number of points you should be aware of before you start preparing the data:
Figure 4-5, Segment Size Array Example
1. Each channel pair has its own segment table buffer. Therefore, make sure you selected the correct
```
active channel (with the INST:SEL command) before you download segment table data to the
```
WX2184C
User Manual
4-72
waveform segments into one single waveform. The following figure demonstrates how the new waveform
looks like:
Figure 4-7, Single Segment Download Array Example
Notice that besides the first waveform, each of the following waveforms is artificially expanded by 16 dummy
points right at the beginning of the segment. The value of these points should be the same as the value of
the first point of the waveform segment. So now, the total length of the three waveform segments is
4,000+3,000+5,000+32 = 12,032 points. To download the data the download mode should be COMBined.
This means that the data of both channels in a channel pair should be downloaded together, and therefore
the header for the data download command should be as follows:
TRACe#648128<binary_block>
Where 6 defines that 6 digits will follow and 48128 is the number of bytes that will be downloaded
using the binary download process. Explanation on the TRACe# command is given in the Arbitrary
Waveform Commands section of this manual.
Parameters
Name Type Description
<binary_block> Binary Block of binary data that contains information on the
segment table.
WX2184C
User Manual
4-74
with the output waveform.
With the above in mind, there is a difference between how a digital
pattern is stored in the digital pattern memory and how an arbitrary
waveform is stored in the arbitrary memory. For every arbitrary
waveform point or sample, there are two identical digital patterns
cycles. For example, if you assign a 1024 point segment in the
arbitrary memory, you can assign 1024 different values, while in the
```
digital memory, since each digital pattern (point) is repeated twice
```
you can have a maximum of 512 different digital patterns. This
means that although the memories are sampled at the same rate
the digital pattern is generated at half the rate of the arbitrary
waveform.
Memory segments are described in the Arbitrary Waveform
Commands section so go to this section if you need to use multiple
segments for your patterns sequence however, always bear in mind
that when you assign a certain size to a segment, the number of
patterns that you may load to this segment is only half of the
assigned number as discussed in the previous paragraph.
Additional information is given in the following with the individual
commands that program the digital patterns. Summary of the digital
output control commands is given in Table 4-8.
Table 4-8, Digital Output Control Commands Summary
```
(Available when Digital option is installed only)
```
7. Digital Commands
Keyword Parameter Form Default Notes
:DIGital
:CLOCk SDR | DDR SDR
:PORT 1 | 2 | BOTH BOTH
:PRESent? Return if the POD is
connected or not
[:STATe] OFF | ON | 0 | 1 0 Toggles digital on/off
:DATA #<header><binary_block>
```
:PARameters #<header><binary_block> State (Byte),Delay
```
```
(Double), High (float),
```
```
Low (float)
```
:BIT<N>
:STATe OFF | ON | 0 | 1 0
:DELay -2.5e-9 to 2.5e-9 0
[:LEVel]
:HIGH -1.5 to 2 0.5
:LOW -2 to 1.5 0
:DELay -2.5e-9 to 2.5e-9 0
:MODe COMMon | SEParate COMM
:VOLTage
[:LEVel]
:HIGH -1.5 to 2 0.5
WX2184C
User Manual
4-76
```
:DIGital:PRESent? (?)
```
Description
Use this command to query whether a digital POD is hooked up on the rear-panel digital output connector.
```
There are two connectors on the rear panel. Query port 1 using the commands: dig:port 1;:dig:pres?. To
```
```
query port 2, use the commands: dig:port 2;:dig:pres?.
```
Response
The WX2184C will return 1 if a digital POD is present or 0 if no POD was detected.
```
:DIGital[:STATe]{OFF|ON|0|1}(?)
```
Description
This command will set or query the state of the digital outputs. Note that for safety, the outputs always
default to off, even if the last instrument setting before power down was on. The on/off setting affects all
digital bits simultaneously on each channel.
Parameters
Range Type Default Description
0-1 Discrete 0 Sets the outputs of the digital bits on and off
Response
The WX2184C will return 1 if the digital outputs are ON, or 0 if the digital outputs are OFF.
:DIGital:DATA#<header><binary_block>
Description
This command will download digital data to the WX2182B-D dedicated digital memory. Digital data is
loaded to the WX2182B-D using high-speed binary transfer. A special command is defined by IEEE-STD-
```
488.2 for this purpose. High-speed binary transfer allows any 8-bit bytes (including extended ASCII code) to
```
be transmitted in a message. This command is particularly useful for sending large quantities of data. As an
```
example, when writing to a single port (1 or 2), the next command will download to the generator an
```
arbitrary block of data of 1,024 points
```
This command causes the transfer of 2048 bytes of data (1024 digital patterns) into the digital memory.
```
The <header> is interpreted this way:
```
The ASCII "#" ($23) designates the start of the binary data block.
```
"4" designates the number of digits that follow.
"2,048" is the even number of bytes to follow.
Note that:
In order to download a 1,024 point block of digital data it is necessary to define a segment length of
2,048
WX2184C
User Manual
4-78
Parameters
Name Type Description
<header> Discrete Provides information on the size of the binary block
that contains pattern data.
<binary_block> Binary Block of binary data that contains pattern data points,
as explained above.
:DIGital:PARameters#<header><binary_block>
Description
This command will download an array of controls for the digital outputs. This array programs all bits
simultaneously for their low and high voltage level and their relative delay in reference to the reference bit.
Parameter data for the digital bits is loaded to the WX2184C using high-speed binary transfer using the
same technique as was described for the digital data download. Check the :DIGital:DATA# command
above for information on the high-speed binary transfer preparation and download sequence.
The digital parameters data is made of 17 byte. Figure 4-10 shows a parameter sequence that is
acceptable for the WX2184C when writing to a single port. Note that the last two bits are not available as a
POD output and therefore data in those bytes is irrelevant for the programming sequence. Also, when
writing to both ports there are 32 bits so when connected to two 14-bit pods bits 15,16, 31 and 32 are
irrelevant
Figure 4-10, 17 Bytes Digital Pattern Parameters Data Representation
Note in the above:
Delay is programmed with 8 bytes double float
High and low levels are programmed with 4 bytes float
WX2184C
User Manual
4-80
```
:DIGital:BIT<n>:LEVel[:HIGH]<hi_level>(?)
```
Description
Use this command to set or query the high level value for individual bits. This command does not affect the
outputs when dig:volt:mode option is common.
Parameters
Name Range Type Default Description
<hi_level> -1.5 to 2.0 Numeric 0.5 Will set high level value for a specific bit <n>. The
high level is programmed in units of volts.
Response
The WX2184C will return the present high level value in units of volts. The returned value will be in
```
standard scientific format (for example: -100 mV would be returned as -100e-3 positive numbers are
```
```
unsigned).
```
```
:DIGital:BIT<n>:LEVel:LOW<lo_level>(?)
```
Description
Use this command to set or query the low level value for individual bits. This command does not affect the
outputs when dig:volt:mode option is common.
Parameters
Name Range Type Default Description
<low_level> -2.0 to 1.5 Numeric 0 Will set low level value for a specific bit <n>. The high
level is programmed in units of volts.
Response
The WX2184C will return the present high level value in units of volts. The returned value will be in
```
standard scientific format (for example: -100 mV would be returned as -100e-3 positive numbers are
```
```
unsigned).
```
```
:DIGital:DELay<delay>(?)
```
Description
Use this command to set or query the global delay for the digital output bits. Delay is referenced to the non-
delayed position of the digital bit. This command does not affect the outputs when dig:del:mode option is
separate.
Parameters
Name Range Type Default Description
<delay> -2.00e-9 to 2.00e-9 Numeric 0 Will set a global delay value for all digital bits. The
delay is referenced to the 0-delay position and is
WX2184C
User Manual
4-82
Parameters
Name Range Type Default Description
<lo_level> -2.0 to
1.5
Numeric 0 Will set low level value for all digital bits. The low
level is programmed in units of volts.
Response
The WX2184C will return the present low level value in units of volts. The returned value will be in standard
```
scientific format (for example: -100 mV would be returned as -100e-3 positive numbers are unsigned).
```
```
:DIGital:VOLTage:MODE{COMMon|SEParate}(?)
```
Description
This command will set or query the state of the digital voltage setting.
Parameters
Name Type Default Description
COMMon Discrete COMM Sets the voltage mode to common. The dig:volt:high and
```
dig:volt:low commands will jointly affect the amplitude level
```
parameter of all digital bits.
SEParate Discrete Sets the voltage mode to separate. The dig:bit<n>:lev and
```
dig:bit<n>:lev low commands will affect the amplitude level
```
parameter of a specific digital bit.
Response
The WX2184C will return COMM or SEP, depending on the present digital voltage mode.
WX2184C
User Manual
4-84
```
Table 4-9, Sequence Control Commands (Continued)
```
Keyword Parameter Form Default Notes
:COUPle <1 to 1,000>,<1 to 1,000>
:SOURce BUS | EXTernal BUS Toggle control source
:TIMing COHerent | IMMediate COH Jump timing
:PREStep WAVE | DC WAVE DC is active in
continuous and BUS
source only
:ONCe
:COUNt 1 to 16,777,216
:SYNC
[:LOCK] <step_number> 1 Sync position
```
:SEQuence:ADVance{AUTOmatic|ONCE|STEPped}(?)
```
Description
This command will select the sequence advance mode. It defines how the output advances through the
sequence steps. There are three advance modes: automatic, once and stepped.
In automatic advance mode, the routine goes through the steps automatically and if there are no jump flag,
the sequence will end and then start over automatically. If a loop counter other than 1 is programmed for a
specific step in the sequence, the step will loop n times and then automatically advance to the next step.
The jump flag inhibits the progression to the next step until a valid signal at the event input releases the
step to jump.
In once advance mode, the routine goes through the steps automatically and if there are no jump flags, the
sequence will end and idle on a specific waveform, depending on the selected run mode. If the once
counter is programmed to a value other than 1, the sequence will repeat itself n times. If a loop counter
other than 1 is programmed for a specific step in the sequence, the step will loop n times and then
automatically advance to the next step. The jump flag inhibits the progression to the next step, until a valid
signal at the event input releases the step to jump.
In stepped advance mode, the routine goes through the steps only after a valid event signal. When the
sequence is complete, the sequence repeats itself with valid event signals. Jump flags are ignored in
stepped mode, but a loop counter other than 1 will repeat the step for n times with each event, before
advancing to the next step.
Parameters
Name Type Default Description
AUTOmatic Discrete AUTO Specifies continuous advance where the generator
steps continuously to the end of the sequence table
and repeats the sequence from the start. For
example, if a sequence is made of three segments 1,
2 and 3, the sequence will generate an infinite
number of
```
each link (segment) can be programmed with its
```
```
associated loop (repeat) number and jump flag to
```
inhibit advancement until an event signal has been
received.
WX2184C
User Manual
4-86
There are a number of points you should be aware of before you start preparing the data:
1. Each channel has its own sequence table buffer. Therefore, make sure you select the correct active
```
channel (with the INST:SEL command) before you download sequence table data to the generator
```
2. Minimum number of sequencer steps is 3; maximum number is 32,768
3. The number of bytes in a complete sequence table must divide by 8. The Model WX2184C has no
control over data sent to its sequence table during data transfer. Therefore, wrong data and/or
incorrect number of bytes will cause erroneous sequence partition
4. Step numbers are assigned automatically in the same order as the structure is built. The first 8-byte
structure forms step number 1 and the last, form step number n. As an example, for 100 steps
```
sequence, one should build an array of 100 seqTableEntry t; entries.
```
Figure 4-11, 64-bit Sequence Table Download Format
Parameters
Name Type Default Description
<header> Discrete Sequence table header, defines the length of the binary
<data_array>.
<data_array> Binary Block of binary data that contains information on the
sequence table.
:SEQuence:DEFine<step>,<segment_#>,<loops>,<jump_flag>
Description
Use this command to create a sequence table. It defines all of the parameters that are associated
with the sequence step such as: step number, segment number, loops and jump flag. Each step
in a sequence table must be programmed separately, except if the seq:data command is used to
download a complete table in binary code. The seq:leng command can be used to first predefine
the length of the sequence table. However, the length is adjusted automatically to the number of
entries when the seq:def commands program each step.
Parameters
Name Range Type Description
<step> 1 to
49,152
```
Numeric (integer
```
```
only)
```
Programs the step in the sequence table. Steps are
indexed from 1 to 49,152 and must be programmed in an
ascending order. Empty step locations in a sequence table
are not permitted. Minimum number of steps required to
create a sequence is 3.
WX2184C
User Manual
4-88
```
:SEQuence:JUMP{BUS|EVENt}(?)
```
Description
Use this command to set or query the source of the jump signal. The jump signal is required for Auto and
Stepped advance sequence modes. In Auto advance mode, the sequence will advance through the steps
valid jump signal is asserted. In Stepped mode, the jump signal is required for every step to advance to the
next waveform in the sequence ladder.
Parameters
Name Type Default Description
BUS Discrete BUS Defines that the sequence will advance to the next
step only when a remote trigger command such as
*trg has been received.
EVENt Discrete Defines that the sequence will advance to the next
step only when a valid signal has been asserted to
the Event input.
Response
The WX2184C will return BUS, or EVEN depending on the present sequence jump setting.
```
:SEQuence:LENGth<length >(?)
```
Description
Use this command to define or query the number of steps that will be programmed in a specific sequence
table. Note that this command is optional if you program the sequence table using the seq:data# command,
as this later command will automatically build the table with the number of programmed steps.
Parameters
Name Range Type Default Description
<length> 3 to
49,152
Numeric
```
(integer only)
```
3 Defines the number of steps that will be
programmed in a specific sequence table.
Response
The WX2184C will return the present length value of the active sequence.
```
:SEQuence:SELect<sequence_#>(?)
```
Description
Use this command to query or select an active sequence number to be generated at the output connector.
Each channel can store up to 1,000 different sequence tables. By selecting the active sequence, successive
```
seq:def commands will affect the selected sequence only.
```
WX2184C
User Manual
4-90
Parameters
Name Type Default Description
BUS Discrete BUS Defines that sequences will be switched only when a
remote command has been received.
EXTernal Discrete Defines that the sequence control is transferred to a
rear panel connector. The connector has 8 bits of
parallel control lines that can switch between up to
256 sequences.
Response
The WX2184C will return BUS, or EXT depending on the present sequence select setting.
```
:SEQuence:SELect:TIMing{COHerent|IMMediate}(?)
```
Description
Use this command to set or query the timing characteristics of the sequence select command. This defines
how the generator transitions from sequence to sequence. Use the coherent option to let the sequence
complete, before it jumps to the next sequence. Applications that require an unconditional jump can use the
immediate option, where the generation of the current sequence is aborted and the new sequence is
started immediately thereafter. This command affects the sequence transition timing, regardless if the
sequence control is from remote or from the rear panel connector.
Parameters
Name Type Default Description
COHerent Discrete COH Defines that when a new sequence is selected, the
transition to the new sequence will occur only when
the current sequence has reached its end point.
IMMediate Discrete Defines that when a new sequence is selected, the
current sequence will be aborted and the transition to
the new sequence will occur immediately, without
waiting for the current sequence to reach its end
point.
Response
The WX2184C will return COH, or IMM depending on the present sequence select timing setting.
```
:SEQuence:PREStep{WAVE|DC}(?)
```
Description
This command is valid only for armed continuous operation and where the selected arming event is BUS.
This command is available from remote only and will not operate from exercising front panel controls. This
command modifies the normal operation of the sequencer in such a way that it places a blank DC segment in
front of the sequence table so, the first time the sequence is selected, a DC signal is present at the output
and when triggered for the first time, the sequences steps to its first active waveform in the sequence table.
At the end of the sequence, the sequence repeats itself without using the blank DC pre-step until aborted by
the user.
WX2184C
User Manual
4-92
Advanced
Sequencing
Control
Commands
This group is used to control a special incidence of the sequence
generator where sequences, and not segments, are sequenced.
Unlike the standard sequence generator that can store up to 1000
different sequence scenarios, the advanced sequencing generator
can store only one sequence.
Generating an Advanced Sequence
The advanced sequence generator is similar to the standard
sequence generator, except the sequence is made of sequences
that were preloaded and stored in individual sequence tables. The
advanced sequence generator has the ability to link and loop these
sequences in user-programmable order.
If you already built and used standard sequence tables then the
procedure of building an advanced sequencing table is very similar.
There are a number of tools that you can use to build an advanced
sequencing table.
In general, the advanced sequence table is built one step at a time
using the aseq:def command. The one-step method is slow and
tedious. However, it allows better control for someone who is just
beginning their first sequence programming. Use the information
below to understand the advanced sequencing commands and how
to implement them in your application.
The advanced sequencing commands are listed in Table 4-10.
Factory defaults after *RST are shown in the Default column.
Parameter range and low-and high-limits are listed, where
applicable.
Table 4-10, Sequence Control Commands
Keyword Parameter Form Default Notes
[:SOURce]
:ASEQuence
:ADVance AUTOmatic | ONCE | STEPped AUTO
:DEFine <step>,<sequence_#>,<loops>,<jump_flag> 3 step is minimum
:DELete Deletes table
:LENGth 3 to 1,000 Optional definition
:ONCe
:COUNt 1 to 1,048,575
:SYNC
:LOCK <1 to 1,000> 1 Sync position
WX2184C
User Manual
4-94
:ASEQuence#<header><data_array>
Description
This command will build a complete advanced sequence table in one binary download. In this way, there is no
need to define and download individual sequence steps. Using this command, sequence table data is loaded
to the WX2184C using high-speed binary transfer in a similar way to downloading waveform data with the
```
trace command. High-speed binary transfer allows any 8-bit bytes (including extended ASCII code) to be
```
transmitted in a message. This command is particularly useful for long sequences that use a large number of
sequences. As an example, the next command will generate three-step sequence with 24 bytes of data that
contains sequence number, loops and jump flag option.
```
This command causes the transfer of 24 bytes of data (3-step sequence) to the advanced sequence table
```
buffer. The <header> is interpreted this way:
```
The ASCII "#" ($23) designates the start of the binary data block.
```
"2" designates the number of digits that follow.
"24" is the number of bytes to follow. This number must divide by 8.
The generator accepts binary data as 64-bit integers, which are sent in two-byte words. Therefore, the total
number of bytes is always eight times the number of sequence steps. For example, 24 bytes are required to
download 3 sequence steps to the advanced sequence table. The transfer of definite length arbitrary block
```
data must terminate with the EOI bit set. This way, carriage-return (CR 0dH) and line feed (LF 0aH)
```
characters can be used as sequence data and will not cause unexpected termination of the arbitrary block
data.
The code below demonstrates the data structure and the below figure shows how to prepare the 64-bit word
for the sequence step, number of loops and jump flag option.
There are a number of points you should be aware of before you start preparing the data:
1. Each channel has its own advanced sequence table buffer. Therefore, make sure you select the correct
```
active channel (with the INST:SEL command) before you download sequence table data to the
```
generator
2. Minimum number of advanced sequencer steps is 3; maximum number is 32,768
3. The number of bytes in a complete sequence table must divide by 8. The Model WX2184C has no
control over data sent to its sequence table during data transfer. Therefore, wrong data and/or
incorrect number of bytes will cause erroneous sequence partition
4. Step numbers are assigned automatically in the same order as the structure is built. The first 8-byte
structure forms step number 1 and the last, form step number n. As an example, for 100 steps
```
sequence, one should build an array of 100 AseqTableEntry t; entries.
```
WX2184C
User Manual
4-96
a specific step.
specifies that the output will dwell on the current step and
will circulate to the next step only after a valid event has
been received.
TIP
The WX2184C attempts to rebuild the sequence table and restart the sequence every
time you use the aseq:def command and while your generator is sequencing.
Therefore, sending this command in sequenced mode will slow the programming
process and the operation of the generator. Using the aseq:def command in FIX or
USER mode will greatly speed up programming time.
:ASEQuence:DELete
Description
Use this command to delete and reset the contents of the advanced sequencing table. No variables are
associated with this command, because there is only one table available in the system.
```
:ASEQuence:LENGth<length >(?)
```
Description
Use this command to define or query the number of steps that will be programmed in the advanced
sequencing table. Note that this command is optional if you program the table using the aseq:data#
command, as this later command will automatically build the table with the number of programmed steps.
Parameters
Name Range Type Default Description
<length> 1 to
1,000
Numeric
```
(integer only)
```
1 Defines the number of steps that will be
programmed in the advanced sequencing table.
Response
The WX2184C will return the present length value of the sequence table.
```
:ASEQuence:ONCE:COUNt<loops>(?)
```
Description
Use this command to set or query the number of loops that the advanced sequence will execute when its
advance mode is programmed to ONCE. If a value other than 1 is programmed in the once counter
database, then the sequence will execute to its last waveform and return to an idle state. The sequence
repeats n times, depending on the setting of the aseq:once:coun command.
WX2184C
User Manual
4-98
Modulated
Waveforms
Global Control
Commands
This group is used to set up the instrument in modulated waveforms
mode and to select the general parameters that control all
modulation functions. Note that the modulation can be turned off to
```
create continuous carrier waveforms (CW). The following
```
modulation schemes can be selected and controlled: AM, FM,
Sweep, Chirp, FSK, ASK, Frequency Hopping, Amplitude Hopping,
```
(n)PSK and (n)QAM. The modulated waveforms global control
```
commands are summarized in Table 4-11. Factory defaults after
*RST are shown in the Default column. Parameter range and low
and high limits are listed, where applicable.
Note that when working in uncoupled mode modulations are set for
each channel pair, so for example CH1&CH2 share the same
modulation settings.
Table 4-11, Modulated Waveforms Global Commands
Keyword Parameter Form Default Notes
[:SOURce]
:MODulation
:TYPE OFF | AM | FM | SWEep | CHIRp | FSK | ASK |
FHOPping | AHOPping | PSK | QAM
OFF
:CARRier
[:FREQuency] 10e3 to 1e9 1e6
:FUNCtion SINusoid | TRIangle | SQUare SIN
```
:MODulation:TYPE{OFF|AM|FM|SWEep|CHIRp|FSK|ASK|FHOPping|
```
```
AHOPping|PSK|QAM }(?)
```
Description
This command selects the modulation type. All modulation types are internal, so external signals are not
required for producing modulation.
Parameters
Name Type Default Description
OFF Discrete OFF Modulation off is a special mode where the output
generates continuous, non-modulated sinusoidal
```
carrier waveforms (CW).
```
AM Discrete This turns on the AM function. Program the AM
parameters to fine-tune the function for your
application.
FM Discrete This turns on the FM function. Program the FM
parameters to fine-tune the function for your
application.
SWEep Discrete This turns on the sweep function. Program the sweep
parameters to fine-tune the function for your
application.
WX2184C
User Manual
4-100
```
:MODulation:CARRier:FUNCtion(SINusoid|TRIangle|SQUare}(?)
```
Description
This specifies the carrier function. There are three functions that can be modulated: Sine, Triangle and
Square. The sine, triangle and the square are computed and placed in the memory as complete waveforms
and the modulation schemes are computed and replayed as arbitrary waveforms.
Parameters
Name Type Default Description
SINusoid Discrete SIN Selects sine as the modulated waveform
TRIangle Discrete Selects triangle as the modulated waveform
SQUare Discrete Selects square as the modulated waveform
Response
The WX2184C will return SIN, TRI, or SQU depending on the selected waveform setting.
WX2184C
User Manual
4-102
```
Table 4-12, Modulated Waveforms Control Commands (Continued)
```
Keyword Parameter Form Default Notes
:FREQuency
[:STARt] 10e3 to 1000e6 40e6
:STOP 10e3 to 1000e6 80e6
:DIRection UP | DOWN UP
:SPACing LINear | LOGarithmic LIN
:MARKer
[:FREQuency] 10e3 to 1000e6 60e6
:AMPLitude
:DEPTh 0 to 100% 50%
:DIRection UP | DOWN UP
:SPACing LINear | LOGarithmic LIN
:FSK
:FREQuency
:SHIFted 10e3 to 1000e6 10e6
:BAUD 0.1 to 500e6 10e3
:MARKer 1 to 256 1
:DATA <data_array>
:ASK
[:AMPLitude]
[:STARt] 0 to 2 2
:SHIFted 0 to 2 1
:BAUD 0.1 to 500e6 10e3
:MARKer 1 to 256 1
:DATA <data_array>
:FHOPping
:DWELl
:MODe FIXed | VARiable FIX
[:TIMe] 2e-9 to 10 5e-6
:FIXed
:DATA <data_array>
:VARiable
:DATA <data_array>
:MARKer 1 to 256 1
:AHOPping
:DWELl
:MODe FIXed | VARiable FIX
[:TIMe] 2e-9 to 10 5e-6
:FIXed
:DATA <data_array>
:VARiable
:DATA <data_array>
:MARKer 1 to 256 1
WX2184C
User Manual
4-104
AM Programming Use the following command for programming the AM parameters. AMcontrol is internal. The commands for programming the amplitude
modulation function are described below. Note that the carrier
```
waveform frequency (CW) setting is common to all modulation
```
schemes.
```
:AM:FUNCtion:SHAPe(SINusoid|TRIangle|SQUare|RAMP}(?)
```
Description
This command will select one of the waveform shapes as the active modulating waveform.
Parameters
Name Type Default Description
SINusoid Discrete SIN Selects the sine shape as the modulating waveform
TRIangle Discrete Selects the triangular shape as the modulating
waveform
SQUare Discrete Selects the square shape as the modulating
waveform
RAMP Discrete Selects the ramp shape as the modulating waveform
Response
The WX2184C will return SIN, TRI, SQU, or RAMP depending on the selected function shape setting.
```
:AM:INTernal:FREQuency<am_freq>(?)
```
Description
This command will set the modulating wave frequency for the built-in standard modulating waveform library.
Parameters
Name Range Type Default Description
<am_freq> 100 to
1e6
Numeric 1e3 Programs the frequency of the modulating waveform
in units of Hz. The frequency of the built-in standard
modulating waveforms only is affected. Note that
maximum carrier-to-internal-frequency-ratio is 1e6.
Response
The WX2184C will return the present modulating waveform frequency value. The returned value will be in
```
standard scientific format (for example: 100mHz would be returned as 100e-3 positive numbers are
```
```
unsigned).
```
WX2184C
User Manual
4-106
SQUare Discrete Selects the square shape as the modulating
waveform
RAMP Discrete Selects the ramp shape as the modulating waveform
Response
The WX2184C will return SIN, TRI, SQU, or RAMP depending on the selected function shape setting.
```
:FM:FREQuency<fm_freq>(?)
```
Description
This command will set the modulating wave frequency for the built-in standard modulating waveform library.
Parameters
Name Range Type Default Description
<fm_freq> 100 to
100e6
Numeric 10e3 Programs the frequency of the modulating waveform
in units of Hz. Only the frequency of the built-in
standard modulating waveforms is affected.
Response
The WX2184C will return the present modulating waveform frequency value. The returned value will be in
```
standard scientific format (for example: 100mHz would be returned as 100e-3 positive numbers are
```
```
unsigned).
```
```
:FM:MARKer<frequency>(?)
```
Description
This function programs marker frequency position. An FM marker can be placed inside the following range:
```
(carrier frequency ± deviation frequency / 2). The marker pulse is output from the SYNC output connector.
```
Parameters
Name Range Type Default Description
<frequency> 10e3 to
1000e6
Numeric 1e6 Programs the marker frequency position in units of
Hz.
Response
The WX2184C returns the present marker frequency value. The returned value will be in standard scientific
```
format (for example: 100mHz would be returned as 100e-3 positive numbers are unsigned).
```
Sweep Modulation
Programming
Use the following command for programming the sweep
parameters. Sweep control is internal. The frequency will sweep
from start to stop frequencies at an interval determined by the
sweep time value and controlled by a step type determined by the
sweep step parameter.
WX2184C
User Manual
4-108
```
:SWEep:TIMe<time>(?)
```
Description
This specifies the time that will take the WX2184C to sweep from start-to-stop frequencies. The time does
not depend on the sweep boundaries, as it is automatically adjusted by the software to the required interval.
At the end of the sweep cycle, the output waveform maintains the sweep stop frequency setting, except if
the WX2184C is in continuous run mode, where the sweep repeats itself continuously.
Parameters
Name Range Type Default Description
<time> 1.4e-6
to 0.01
Numeric 10e-6 Programs the sweep time. Sweep time is
programmed in units of s.
Response
The WX2184C will return the present sweep time. The returned value will be in standard scientific format
```
(for example: 100ms would be returned as 100e-3 positive numbers are unsigned).
```
```
:SWEep:DIRection(UP|DOWN}(?)
```
Description
```
This specifies if the WX2184C output will sweep from start-to-stop (UP) or from stop-to-start (DOWN)
```
frequencies. Sweep time does not affect the sweep direction and frequency limits. At the end of the sweep
cycle, the output waveform normally maintains the sweep stop frequency setting, but will maintain the start
frequency if the DOWN option is selected, except if the WX2184C is in continuous run mode where the
sweep repeats itself continuously.
Parameters
Name Type Default Description
UP Discrete UP Selects the sweep up direction
DOWN Discrete Select the sweep down direction
Response
The WX2184C will return UP, or DOWN depending on the selected direction setting.
```
:SWEep:SPACing(LINear|LOGarithmic}(?)
```
Description
This specifies the sweep step type. Two options are available: logarithmic or linear. In linear, the
incremental steps between the frequencies are uniform throughout the sweep range. Logarithmic type
defines logarithmic spacing throughout the sweep start and stop settings.
Parameters
Name Type Default Description
LINear Discrete LIN Selects the linear sweep spacing
LOGarithmic Discrete Select the logarithmic sweep spacing
WX2184C
User Manual
4-110
```
:CHIRp:REPetition<interval>(?)
```
Description
Use this command to set or query the time interval between consecutive chirp cycles. The time is measured
between two adjacent chirp starts.
Parameters
Name Range Type Default Description
<interval> 200e-9
to 20
Numeric 25e-6 Programs the intervals between adjacent chirp
cycles. Chirp repetition is programmed in units of
seconds.
Response
The WX2184C will return the present chirp repetition value. The returned value will be in standard scientific
```
format (for example: 100ms would be returned as 100e-3 positive numbers are unsigned).
```
```
:CHIRp:FREQuency[:STARt]<start_freq>(?)
```
Description
Use this command to set or query the start frequency within the chirp cycle. Start and stop frequencies can
be identical for non-swept chirps but could also be different is frequency sweep is required within a single
chirp cycle.
Parameters
Name Range Type Default Description
<start_freq> 10e3 to
1e9
Numeric 40e6 Programs the chirp start frequency. Chirp start
frequency is programmed in units of seconds.
Response
The WX2184C will return the present chirp start frequency value. The returned value will be in standard
```
scientific format (for example: 100ms would be returned as 100e-3 positive numbers are unsigned).
```
```
:CHIRp:FREQuency:STOP<stop_freq>(?)
```
Description
Use this command to set or query the stop frequency within the chirp cycle. Start and stop frequencies can
be identical for non-swept chirps but could also be different is frequency sweep is required within a single
chirp cycle.
Parameters
Name Range Type Default Description
<start_stop> 10e3 to
1e9
Numeric 80e6 Programs the chirp stop frequency. Chirp start
frequency is programmed in units of seconds.
Response
The WX2184C will return the present chirp stop frequency value. The returned value will be in standard
```
scientific format (for example: 100ms would be returned as 100e-3 positive numbers are unsigned).
```
WX2184C
User Manual
4-112
```
:CHIRp:AMPLitude:DEPTh<index>(?)
```
Description
Use this command to set or query the chirp amplitude modulation index. Chirp amplitude can be modulated
up or down, depending on the chirp direction setting.
Parameters
Name Range Type Default Description
<index> 0 to 100 Integer 50 Programs the chirp amplitude modulation index in
units of %.
Response
The WX2184C will return the present amplitude modulation index value. The returned value will be an
integer.
```
:CHIRp:AMPLitude:DIRection(UP|DOWN}(?)
```
Description
Use this command to set or query the chirp amplitude direction. The start and stop amplitude settings is
determined by the chirp amplitude modulation depth.
Parameters
Name Type Default Description
UP Discrete UP Selects the chirp amplitude modulation up direction
DOWN Discrete Select the chirp amplitude modulation down direction
Response
The WX2184C will return UP or DOWN, depending on the selected chirp amplitude direction setting.
```
:CHIRp:AMPLitude:SPACing(LINear|LOGarithmic}(?)
```
Description
Use this command to set or query the chirp amplitude spacing. Two options are available: logarithmic or
linear. In linear, the incremental steps between the amplitudes are uniform throughout the chirp range.
Logarithmic type defines logarithmic amplitude spacing throughout the chirp start and stop settings.
Parameters
Name Type Default Description
LINear Discrete LIN Selects the linear chirp amplitude spacing
LOGarithmic Discrete Select the logarithmic chirp amplitude spacing
Response
The WX2184C will return LIN or LOG, depending on the selected chirp amplitude spacing setting.
WX2184C
User Manual
4-114
Parameters
Name Range Type Default Description
<index> 1 to 256 Numeric
```
(integer only)
```
1 Programs a marker pulse at an index bit position.
Response
The WX2184C will return the present marker position.
:FSK:DATA<fsk_data>
Description
Loads the data stream that will cause the WX2184C to hop from carrier to shifted frequency and vice versa.
Data format is a string of "0" and "1" which define when the output generates carrier frequency and when it
shifts frequency to the FSK value. "0" defines carrier frequency,"1" defines shifted frequency. Note that if
you intend to program marker position, you must do it before you load the FSK data list.
Below you can see how an FSK data table is constructed. The sample below shows a list of 10 shifts. The
WX2184C will step through this list, outputting either carrier or shifted frequencies, depending on the data
```
list: Zero will generate carrier frequency and One will generate shifted frequency. Note that the waveform is
```
always sinewave and that the last cycle is always completed.
Sample FSK Data Array
0 1 1 1 0 1 0 0 0 1
Parameters
Name Type Description
<fsk_data> ASCII Block of ASCII data that contains information for the
generator when to shift from carrier to shifted
frequency and visa versa.
WX2184C
User Manual
4-116
Parameters
Name Range Type Default Description
<rate> 0.1 to
500e6
Numeric 10e3 Programs the rate of which the frequency shifts from
carrier to shifted frequency in units of Hz.
Response
The WX2184C will return the present baud value. The returned value will be in standard scientific format
```
(for example: 100kHz would be returned as 100e3 positive numbers are unsigned).
```
```
:ASK:MARKer<index>(?)
```
Description
Programs where on the data stream the WX2184C will generate a pulse, designated as ASK marker, or
index point. The marker pulse is generated at the SYNC output connector. Note that if you intend to
program marker position, you must do it before you load the ASK data list.
Parameters
Name Range Type Default Description
<index> 1 to 256 Numeric
```
(integer only)
```
1 Programs a marker pulse at an index bit position.
Response
The WX2184C will return the present marker position.
:ASK:DATA<ask_data>
Description
Loads the data stream that will cause the WX2184C to hop from one amplitude level to shifted amplitude
level and vice versa. Data format is a string of "0" and "1" which define when the output generates base
level and when it shifts amplitude to the ASK value. "0" defines base level amplitude,"1" defines shifted
amplitude level. Note that if you intend to program marker position, you must do it before you load the ASK
data list.
Below you can see how an ASK data table is constructed. The sample below shows a list of 10 shifts. The
2572A will step through this list, outputting either base or shifted amplitudes, depending on the data list:
Zero will generate base level and One will generate shifted amplitude. Note that the waveform is always
sinewave and that the last cycle is always completed.
Sample ASK Data Array
0 1 1 1 0 1 0 0 0 1
Parameters
Name Type Description
<ask_data> ASCII Block of ASCII data that contains information for the
generator when to shift from base to shifted
WX2184C
User Manual
4-118
Response
The WX2184C will return the present dwell time value. The returned value will be in standard scientific
```
format (for example: 100 ms would be returned as 100e-3 positive numbers are unsigned).
```
:FHOP:FIX:DATA<fix_hop_data>
Description
This command will download the data array that will cause the instrument to hop through the frequency list.
The dwell time for each frequency list item is fixed and can be programmed using the HOP:DWEL
command. Note that if you intend to program marker position, you must do it first and then load the
frequency hops list.
Below you can see how a hop table is constructed. The file sample below shows a list of 10 frequencies.
The WX2184C will hop through this list, outputting the next frequency each time it hops. Note that the
carrier waveform is always sinewave and that the last cycle is always completed even if the dwell time is
shorter than the period of the waveform. For example, if you program dwell time of 1ms and the frequency
```
step has frequency of 1Hz (1s period), the frequency step will last 1 second although the dwell time is 1ms.
```
Sample Frequency Hops Data Array
1e+6 2e+6 3e+3 4e+6 5e+5 6e+2 7e+1 8e+6 9e+3 10e+5
Parameters
Name Type Description
<fix_hop_data> Double Block of binary data that contains information of
frequency values.
:FHOP:VARiable:DATA<var_hop_data>
Description
This command will download the data array that will cause the instrument to hop through the frequency list.
The dwell time for each frequency list item is variable and is supplied in the variable hop table data array.
Note that the HOP:DWEL command has no effect on this sequence. Also note that if you intend to program
marker position, you must do it first and then load the frequency hops list.
Below you can see how a hop table is constructed. The file sample below shows a list of 10 frequencies
and their associated dwell times. The WX2184C will hop through this list, outputting the next frequency
each time it hops. Note that the carrier waveform is always sinewave and that the last cycle is always
completed even if the dwell time is shorter than the period of the waveform. For example, if you program
```
dwell time of 1 ms and the frequency step has frequency of 1Hz (1s period), the frequency step will last 1
```
second although the dwell time is 1 ms.
Sample Frequency Hops Data Array
1e+6 100e-6 2e+6 200e-6 3e+3 3e-4 4e+6 40e-2 5e+5 5e-3 6e+2 600e-6 7e+1 0.7 8e6 1e-6 9e+3 90e-6
10e+5 100e-6
WX2184C
User Manual
4-120
Amplitude Hopping
Modulation
Programming
Use the following command for programming the amplitude hop
parameters. Hop control is internal. The amplitude will hop from
amplitude level to amplitude level at a rate determined by the dwell
time value and controlled by a sequence of amplitudes in the HOP
data table.
There are two hop modes: Fixed Dwell, where the rate of which the
generator hops from amplitude level to amplitude level is constant
and Variable Dwell, where the rate of which the generator hops from
amplitude level to amplitude level is programmable for each hop.
The commands for programming the amplitude hopping function are
```
described below. Note that the carrier waveform frequency (CW)
```
setting is common to all modulation schemes.
```
:AHOP:DWELl:MODe(FIXed|VARiable}(?)
```
Description
This selects between fixed or variable dwell-time for the amplitude hops. Select the fixed option if you want
each amplitude level to dwell equally on each step. The variable option lets you program a different dwell
time value for each amplitude hop. The WX2184C output hops from one amplitude level to the next
according to a sequence given in a hop table. The variable dwell time table contains dwell time data for
each step however, the fixed dwell time table does not contain any dwell time information and therefore, if
you select the fixed option, make sure your dwell time is programmed as required.
Parameters
Name Type Default Description
FIXed Discrete Selects the fixed dwell time amplitude hops mode
VARiable Discrete VAR Select the variable dwell time amplitude hops mode
Response
The WX2184C will return FIX, or VAR depending on the selected dwell setting.
```
:AHOP:DWELl<dwell_time>(?)
```
Description
This selects the dwell time for amplitude hops when the selected mode is Fixed dwell time hops. The dwell
time table in this case does not contain the dwell time per step parameters and therefore, the value which is
programmed with this command remains constant for the entire hop sequence.
Parameters
Name Range Type Default Description
<dwell_time> 2e-9 to
10
Numeric 10e-6 Programs dwell time for the fixed dwell-time
amplitude hop function. The same dwell time will be
valid for each amplitude hop. Dwell time is
WX2184C
User Manual
4-122
Sample Amplitude Hops Data Array
0.1 5e-6 1.2 10e-6 1.3 20e-6 1.4 50e-6 1.5 1e-6 100e-3 100e-9 200e-3 200e-9 300e-3 300e-9 400e-3
400e-9 500e-3 500e-9
In the above example, the first number is the amplitude value and the second number is its dwell time.
Therefore, only even number of sets can be located in this table.
Parameters
Name Type Description
<var_hop_data> Double Block of binary data that contains information of
amplitude hop values and their respective dwell time.
```
:AHOP:MARKer<index>(?)
```
Description
Programs where on the amplitude list the WX2184C will generate a pulse, designated as Hop marker, or
index point. The marker pulse is generated at the SYNC output connector.
Parameters
Name Range Type Default Description
<index> 1 to 256 Numeric
```
(integer only)
```
1 Programs a marker pulse at an index amplitude hop
position.
Response
The WX2184C will return the present marker position.
PSK Modulation
Programming
Use the following command for programming the PSK parameters.
The following commands will be divided into two groups: PSK
```
commands and (n)PSK commands. The PSK function can shift
```
from start to shifted phase setting, within the range of 0 to 360 , at a
frequency determined by the rate value and controlled by a
```
sequence of bits in the PSK data table. The (n)PSK functions use
```
pre-defined table settings. In case the standard table does not suit
```
the application you can design your own (n)PSK data using the
```
User PSK data table entry option. Note that the carrier waveform
```
frequency (CW) setting is common to all modulation schemes.
```
```
:PSK:TYPE{PSK|BPSK|QPSK|OQPSK|8PSK|16PSK|USER}(?)
```
Description
```
This selects between the various (n)PSK modulation schemes. Note that PSK and BPSK are almost
```
identical functions except PSK can be programmed to shift from any phase to any phase and the BPSK
toggles between two pre-determined values only 0 and 180 .
WX2184C
User Manual
4-124
sequence as programmed by the PSK:DATA table.
USER Discrete Selects the User PSK modulation type. There are no
pre-assigned symbols for this mode and therefore, the
symbols must first be designed using the
```
PSK:USER:DATA table. The number of bits are user
```
definable. The symbols are shifts at a rate determined
by the PSK:BAUD command and in a sequence as
programmed by the PSK:DATA table.
Response
The WX2184C will return PSK, BPSK, QPSK, OQPSK, DQPSK, 8PSK, 16PSK, or USER on the selected
PSK type setting.
```
:PSK:PHASe:<start_phase>(?)
```
Description
This programs the start phase of the carrier waveform. The start phase shifts when the pointer in the data
0
Parameters
Name Range Type Default Description
<start_phase> 0 to 360 Numeric 0 Programs the start phase for the carrier waveform in
units of degrees.
Response
The WX2184C will return the present start phase value.
```
:PSK:PHASe:SHIFted<shift_phase>(?)
```
Description
This programs the shifted phase. The phase
Parameters
Name Range Type Default Description
<shift_phase> 0 to 360 Numeric 180 Programs the shift phase for the carrier waveform in
units of degrees.
Response
The WX2184C will return the present shift phase value.
WX2184C
User Manual
4-126
```
:PSK:BAUD<baud>(?)
```
Description
```
This allows the user to select (n)PSK baud. The baud is the interval of which the symbols stream in the
```
```
(n)PSK data array as they are clocked with the baud generator. Note that this command is dedicated for
```
```
programming the (n)PSK modulation function only and will have no effect on the PSK function.
```
Parameters
Name Range Type Default Description
<baud> 0.1 to
500e6
Numeric 10e3 Programs the baud of which the symbols stream in
```
the (n)PSK data table. Baud is programmed in units
```
of Hz.
Response
The WX2184C will return the present baud value. The returned value will be in standard scientific format
```
(for example: 100mHz would be returned as 100e-3 positive numbers are unsigned).
```
```
:PSK:CARRier:STATe{OFF|ON|0|1}(?)
```
Description
```
This command will toggle the carrier waveform (CW) on and off. This command affects all (n)PSK function
```
and has no effect on the PSK function. The carrier off function is especially useful as direct input for I & Q
vector generators that need the digital information only and supply the carrier information separately.
Parameters
Range Type Default Description
0-1 Discrete 1 Sets the carrier output on and off
Response
The WX2184C will return 1 if the output is on, or 0 if the output is off.
:PSK:USER:DATA<user_data>
Description
```
Loads the user phase data for the (n)PSK modulation function. The data contains a list of phase values
```
within the range of 0 to 360 . The user data table is associated with the User PSK function only where
symbols can be freely designed as non-standard vectors. After you enter the symbol data in this table, you
must generate the symbol sequence using the PSK:DATA command, as shown earlier in this section.
Below you can see an example of the User PSK data table. The symbol index is automatically incremented
from 0 to n so there is no need to provide index numbers in this table.
Sample User PSK Symbols Data Array
WX2184C
User Manual
4-128
256QAM Discrete Selects the 256 Quadrature Amplitude Modulation
```
(256QAM) modulation type. 64QAM is a 8-level
```
modulation method that uses 256 phases/amplitude
symbols. The first two bits define at which event of
```
the IQ plane the phase exists (00: upper right, 01:
```
```
upper left, 10: lower left, 11: lower right) and the rest
```
of the 6 bits defines the position of the symbol in each
event.
The instrument steps through these events in a
sequence as listed in the QAM:DATA table and at a
frequency which is programmed using the
```
QAM:BAUD parameter.
```
USER Discrete Selects the User QAM modulation type. There are no
pre-assigned symbols for this mode and therefore,
the symbols must first be designed using the
```
QAM:USER:DATA table. The instrument will then
```
step through the programmed symbols in a sequence
as listed in the QAM:DATA table and at a frequency
which is programmed using the QAM:BAUD
parameter.
Response
The WX2184C will return 16QAM, 64QAM, 256QAM, or USER depending on the selected QAM type
setting.
```
:QAM:BAUD<baud>(?)
```
Description
```
This allows the user to select (n)QAM baud. The baud is the interval of which the symbols stream in the
```
```
(n)QAM data array as they are clocked with the baud generator.
```
Parameters
Name Range Type Default Description
<baud> 0.1 to
500e6
Numeric 10e3 Programs the baud of which the symbols stream in
```
the (n)QAM data table. Baud is programmed in units
```
of Hz.
Response
The WX2184C will return the present baud value. The returned value will be in standard scientific format
```
(for example: 100mHz would be returned as 100e-3 positive numbers are unsigned).
```
```
:QAM:CARRier:STATe{OFF|ON|0|1}(?)
```
Description
```
This command will toggle the carrier waveform (CW) on and off. The carrier off function is especially useful
```
as direct input for I & Q vector generators that need the digital information only and supply the carrier
information separately.
WX2184C
User Manual
4-130
Response
The WX2184C will return the present marker position.
WX2184C
User Manual
4-132
Figure 4-15, Double Pulse Parameters
Table 4-13, Pulse Waveform Commands Summary
Keyword Parameter Form Default Notes
:PULse
:CONFigure TIME | PERCent TIME
:DELay 1e-9 to 1s 100e-6 Delay in sec
:PERCent 0 .01 to 99.99 10 Delay in %
:DOUBle
:DELay 1e-9 to 1s 100e-6 Double del in sec
:PERCent 0 .01 to 99.99 10 Delay in %
:LEVel
[:CONTrol] HLOW | AOFFset | POSitive | NEGative HLOW
:HIGH -2.0 to 2.0 1
:LOW -2.0 to 2.0 0
:AMPLitude 50e-3 to 2 | MINimum | MAXimum 0.5 Amplitude in V
:OFFSet -1 to 1 | MINimum | MAXimum 0 DC offset in volts
:MODE SINGle | DELayed | DOUBle SING
:POLarity NORMal | COMPlement | INVerted NORM
:PERiod 5e-9 to 5s 1e-3
:TRANsition
[:STATe] FAST | LINear | SYMMetrical FAST Transition type
[:LEADing] 1e-9 to 100e-3 100e-6 Rise time in sec
:PERCent 0 .01 to 99.99 10 Rise time in %
:TRAiling 1e-9 to 100e-3 100e-6 Fall time in sec
:PERCent 0 .01 to 99.99 10 Fall time in %
:WIDTh 2e-9 to 5s 200e-6 Width in sec
:PERCent 0 .01 to 99.99 20 Width in %
WX2184C
User Manual
4-134
```
:PULSe:DELay:PERCent<delay>(?)
```
Description
This command will program the delayed interval of which the output idles on the low level, until the first
transition to high level. The delay is measured from the first external trigger transition to the first pulse
transition. Note that this delay does not include the system delay error that is specified in Appendix A. Also
note that the only case where the delay can exceed the value of the period setting is in triggered mode,
where the external trigger intervals determine the period of the pulse.
Parameters
Name Range Type Default Description
<delay> 0.01 to
99.99
Numeric 10 Will set the delay time interval in units of percent. As
shown in Figure 4-14, the delay is measured from
trigger transition to the first pulse transition.
Response
The WX2184C will return the pulse delay value in units of %.
```
:PULSe:DOUBle:DELay<delay>(?)
```
Description
This command will program the delay between two adjacent pulses when the double mode is selected.
Otherwise, the double pulse delay has no effect on the pulse structure. Note that the only case where the
delay can exceed the value of the period setting is in triggered mode, where the trigger interval determines
the period of the pulse. Double pulse building block parameters are shown in Figure 4-15.
Parameters
Name Range Type Default Description
<delay> 1e-9 to 1 Numeric 100e-6 Will set the delay between two adjacent pulses for
the double pulse mode only. The delay is
programmed in units of seconds and is measured
from the last transition of the first pulse to the first
transition of the second pulse. PULS:DOUB:DEL 0
implies that delay is off.
Response
The WX2184C will return the present double pulse delay value in units of seconds.
```
:PULSe:DOUBle:DELay:PERCent<delay>(?)
```
Description
This command will program the delay between two adjacent pulses when the double mode is selected.
Otherwise, the double pulse delay has no effect on the pulse structure. Note that the only case where the
delay can exceed the value of the period setting is in triggered mode, where the trigger interval determines
the period of the pulse. Double pulse building block parameters are shown in Figure 4-15.
WX2184C
User Manual
4-136
Response
The WX2184C will return the present high-level value. The returned value will be in standard scientific
```
format (for example: 100mV would be returned as 100e-3 positive numbers are unsigned).
```
```
:PULSe:LEVel:LOW<low_level>(?)
```
Description
This command programs the low level amplitude of the pulse waveform. The low level is calibrated when
the load impedance is 50 .
Parameters
Name Range Type Default Description
<low_level> -2.0 to
2.0
Numeric 0 Will set the low level of the pulse waveform in units
of volts.
Response
The WX2184C will return the present low-level value. The returned value will be in standard scientific
```
format (for example: 100mV would be returned as 100e-3 positive numbers are unsigned).
```
```
:PULSe:LEVel:AMPLitude{<ampl>|MINumum|MAXimum}(?)
```
Description
This command programs the peak-to-peak amplitude of the pulse waveform. The amplitude is calibrated
when the source impedance is 50 . Note that this value is a duplication of the volt:ampl parameter and
therefore, modifying this parameter in the pulse menu will automatically modify the amplitude setting for the
other instrument functions.
Parameters
Name Range Type Default Description
<ampl> 50e-3 to
2
Numeric 0.5 Will set the amplitude of the pulse waveform in units
of volts. Amplitude setting is always peak-to-peak.
Offset and amplitude settings are independent,
providing that the offset + amplitude do not exceed
the amplitude window, as specified in Appendix A.
<MINimum> Discrete Will set the amplitude to the lowest possible amplitude
```
(50e-3).
```
<MAXimum> Discrete Will set the amplitude to the highest possible
```
amplitude level (2).
```
Response
The WX2184C will return the present pulse amplitude value. The returned value will be in standard
```
scientific format (for example: 100mV would be returned as 100e-3 positive numbers are unsigned).
```
WX2184C
User Manual
4-138
```
are: Normal - where the pulse is generated exactly as programmed, Inverted - where the pulse is inverted
```
about the 0 level base line and Complemented - where the pulse is inverted about its mid-amplitude axis.
Parameters
Name Type Default Description
NORMal Discrete NORM Programs normal pulse output
COMPlement Discrete Programs complemented pulse output
INVerted Discrete Programs an inverted pulse output
Response
The WX2184C will return NORM, COMP or INV depending on the present polarity setting.
```
:PULSe:PERiod<period>(?)
```
Description
```
This command will program the pulse repetition rate (period). Note that with the sum of all parameters,
```
including the pulse width and fall time cannot exceed the programmed pulse period and therefore, it is
recommended that the pulse period be programmed first, before all other pulse parameters. Note that by
selecting the double pulse mode, the pulse period remains unchanged.
Parameters
Name Range Type Default Description
<period> 5e-9 to 5 Numeric 1e-3 Programs the period of the pulse waveform in units
of seconds. The range is extended to 2e6 with option
264.
Response
The WX2184C will return the present pulse period value in units of seconds.
```
:PULSe:TRANsition:STATe{FAST|LINear|SYMMetrical} (?)
```
Description
```
This command will place the pulse output in one of three transition options: 1) Fast - the level transitions
```
```
from high-to-low or low-to-high at the fastest rate that the generator can produce 2) Linear - the level
```
transitions linearly at a programmed rate from low-to-high and from high-to-low and each transition can be
```
programmed to a different rate and 3) Symmetrical - the leading and trailing edges transition exactly at the
```
same rate.
Parameters
Name Type Default Description
FAST Discrete FAST Programs the fast transitions mode. In this mode, the
leading and trailing edges will transition as fast as the
instrument allows.
LINear Discrete Selects linear transitions. Note that unlike analog pulse
generators, the WX2184C can be programmed freely
within the specified boundaries, without the limitation of
WX2184C
User Manual
4-140
```
:PULSe:TRANsition:TRAiling<t_edge>(?)
```
Description
This command will program the interval it will take the trailing edge of the pulse to transition from its high- to
low-level settings. The parameter is programmed in units of seconds. Unlike analog pulse generators, the
WX2184C can be programmed freely within the specified boundaries, without the limitation of transition
ranges that are commonly attributed to analog pulse generators. Note that this parameter will affect the
instrument only when the pulse transition mode is set to linear.
Parameters
Name Range Type Default Description
<T_edge
>
1e-9 to
100e-3
Numeric 1e-3 Will set the trailing-edge transition time parameter in
units of seconds. Note that the sum of all
parameters, including transition times, must not
exceed the programmed pulse period.
Response
The WX2184C will return the present trailing edge transition time value in units of seconds.
```
:PULSe:TRANsition:TRAiling:PERCent<t_edge>(?)
```
Description
This command will program the interval it will take the trailing edge of the pulse to transition from its high- to
low-level settings. The parameter is programmed in units of percentages of the pulse period. Note that this
parameter will affect the instrument only when the pulse transition mode is set to linear and when the pulse
configuration is programmed to percent.
Parameters
Name Range Type Default Description
<l_edge> 0.01 to
99.99
Numeric 10 Will set the trailing-edge transition time parameter in
units of %. Note that the sum of all parameters,
including transition times, must not exceed 100%.
Response
The WX2184C will return the present leading edge transition time value in units of %.
```
:PULSe:WIDth<width>(?)
```
Description
This command will program the pulse width value. Figures 4-13 through 4-15 show how the pulse width
affects the shape of the pulse. Note that the only case where the pulse width can exceed the value of the
period setting is in triggered mode, where the trigger determines the period of the pulse.
Parameters
Name Range Type Default Description
<width> 1e-9 to 1 Numeric 2e-3 Will set the width of pulse in units of seconds. Note
that the sum of all parameters, including the pulse
WX2184C
User Manual
4-144
Table 4-14, Pulse Pattern Commands Summary
Keyword Parameter Form Default Notes
:PATTern
:MODE PRBS | COMPosed PRBS
[: PRBS]
:TYPE PRBS7 | PRBS9 | PRBS11 | PRBS15 | PRBS23 |
PRBS31 | USER
PRBS7
:BAUD 10e-3 to 500e6 10e6
:LEVel 2 | 3 | 4 | 5 2
:HIGH -2.0 to 2.0 1
:LOW -2.0 to 2.0 -1
:LOOPs 1 to 1e6 1
:PREamble 1 to 16e6 1
:LENGth 2 to 16e6 8
:DATA #<header><data_array>
:COMPosed
:TRANsition
:TYPe FAST | LINear FAST Transition type
:FAST
[:DATA] #<header><data_array>
:LINear
:STARt - 2 to +2 0.5
[:DATA] #<header><data_array>
:RESolution 250e-12 to 100e-9 1e-9
:TYPE AUTO | USER AUTO
```
:PATTern:MODE{PRBS|COMPosed}(?)
```
Description
Use this command to set or query the type of pulse pattern that will be generated by the WX2184C output.
There are 6 PRBS types and an additional user-defined PRBS type. The composed option provides access
to special commands that lets you create any pattern and mix fast and linear transitions.
Parameters
Name Type Default Description
PRBS Discrete PRBS Selects one of 6 internal and one user-defined PRBS
sequences. Patt:type selects the required PRBS type.
COMPoser Discrete Selects the free-programming pattern mode. Use this
option if you intend to create complex digital patterns.
These patterns can have fast or linear transitions,
depending on the patt:comp:tran:type setting.
Response
The WX2184C will return PRBS or COMP depending on the present pattern mode setting.
WX2184C
User Manual
4-146
```
:PATTern[:PRBS]:LEVel<level>(?)
```
Description
Use this command to set or query the PRBS voltage level setting. The effect of the level setting is
demonstrated in Figures 4-17 to 4-20. The PRBS high and low levels determine the maximum amplitude
swing while the PRBS levels parameter determine interim symbol levels.
Parameters
Name Range Type Default Description
<level> 2 to 5 Numeric
```
(integer
```
```
only)
```
2 Will set the symbol level, as demonstrated in Figures
4-17 to 4-20.
Response
The WX2184C will return the present PRBS symbol level value.
```
:PATTern[:PRBS]:LEVel:HIGH<high_level>(?)
```
Description
Use this command to set or query the high level voltage for the PRBS pattern. The pattern amplitude will
swing from high to low level setting.
Parameters
Name Range Type Default Description
<high_level> -2.0 to
2.0
Numeric 1 Will set the high level of the PRBS pattern in units of
volts.
Response
The WX2184C will return the present PRBS high-level value. The returned value will be in standard
```
scientific format (for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
```
:PATTern[:PRBS]:LEVel:LOW<low _level>(?)
```
Description
Use this command to set or query the low level voltage for the PRBS pattern. The pattern amplitude will
swing from high to low level setting.
Parameters
Name Range Type Default Description
<low_level> -2.0 to
2.0
Numeric -1 Will set the low level of the PRBS pattern in units of
volts.
Response
The WX2184C will return the present PRBS low-level value. The returned value will be in standard
```
scientific format (for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
WX2184C
User Manual
4-148
```
only)
```
Response
The WX2184C will return the present PRBS memory allocation value.
:PATTern[:PRBS]:DATA#<header><binary_block>
Description
This command will download an array of data for the user-defined PRBS pattern. The data is supplied to
the generator in a form of binary characters, representing levels only. For example, 0,1,1,1,0,0,1,0
```
represents level 2 PRBS pattern; similarly, 1,2,0,3,3,-,1,-,2,-,4,0,0 contains all level which are associated
```
with PRBS level 5 pattern. The data is provided as CHAR binary bytes that translate to ASCII levels 2, 3, 4
and 5. The translation to PRBS levels is done automatically by the generator so that users do not have to
worry about setting levels as long as high and low levels are programmed prior to downloading the PRBS
user data.
Parameters
Name Type Description
<header> Discrete Provides information on the size of the binary block
that follows. Additional information on IEEE-488.2
arbitrary data downloads is available in earlier
descriptions of data downloads.
Contains PRBS pattern data strings.
<binary_block> Binary Block of binary data that contains PRBS pattern data
strings. Each bit is represented by a single character
```
(CHAR).
```
```
:PATTern:COMPosed:TRANsition:TYPE{FAST|LINear}(?)
```
Description
Use this command to set or query the type of transitions that the pulse composer will generate. You cannot
mix fast and linear transitions if you select the fast mode however, if you select the linear mode, you can
still generate pulses that have fast transitions. Note that this command has an effect on the pulse pattern
only when the pattern mode option is COMP.
Parameters
Name Type Default Description
FAST Discrete FAST Using this option, the pulse composer can generate pulse
patterns that have fast transitions only.
LINear Discrete Selects this option if you want ot mix fast and linear
transitions in the pulse patter that you want ot compose.
Response
The WX2184C will return FAST or LIN depending on the present pattern transition setting.
WX2184C
User Manual
4-150
Response
The WX2184C will return the present low-level value. The returned value will be in standard scientific
```
format (for example: 100 mV would be returned as 100e-3 positive numbers are unsigned).
```
:PATTern:COMPosed:LINear[:DATA]#<header><binary_block>
Description
This command will download an array of data for the built-in pulse composer. The composed data is made
of 12 bytes. Figure 4-22 shows a pulse data parameter sequence that is acceptable for the WX2184C-D.
Figure 4-23 demonstrates how the pulse composer interprets the level and duration to generate linear
transitions.
Figure 4-22, Composed Linear Pulse - Data Representation
Note in the above:
Pulse level data is provided in terms of level and duration only. The pulse will be built by defining the
levels and the duration that the level transitions from last to next.
Note the fastest transition that the output can generate is around 400 ps
Note in Figure 4-23:
Initial level defines from what amplitude level the first transition will occur.
Final level 1 defines the slope of which the pulse will transition linearly and Duration 1 defines how long it
will take for the amplitude to reach the end level.
The end level is automatically selected for the start level of the next transition.
Duration set to 0 generates fast transition. The fastest transition that the output can generate is around
400 ps
WX2184C
User Manual
4-152
Parameters
Name Type Default Description
AUTO Discrete AUTO Using this option, the pulse composer will automatically
select the best resolution to build the linear waveform.
USER Discrete Selects this option if you want to select the resolution that
the linear transitions will increment when you build your
required pulse.
Response
The WX2184C will return AUTO or USER depending on the present linear resolution type setting.
WX2184C
User Manual
4-154
```
SYSTem:IP:MASK<mask_adrs>(?)
```
Description
This command programs the subnet mask address for LAN operation. The programming is performed from
the front panel Utility -> Remote Interface -> LAN menu.
Parameters
Name Range Type Description
<mask_adrs> 0 to 255 String Programs the subnet mask address for LAN
operation. Programming must be performed from the
front panel. The current IP address can be observed
on the TCP/IP Network Properties display.
Response
The WX2184C will return the present IP address value similar to the following: 255.255.255.0
```
SYSTem:IP:BOOTp{OFF|ON|0|1}(?)
```
Description
Use this command to toggle BOOTP mode on and off.
Parameters
Range Type Default Description
0-1 Discrete 0 Toggles BOOTP mode on and off. When on, the IP
address is administrated automatically by the system.
Response
The WX2184C will return 0 or 1, depending on the present BOOTP setting.
```
SYSTem:IP:GATeway<gate_adrs>(?)
```
Description
This command programs the gateway address for LAN operation. The programming is performed from the
front panel Utility -> Remote Interface -> LAN menu.
Parameters
Name Range Type Description
<gate_adrs> 0 to 255 String Programs the gateway address for LAN operation.
Programming must be performed from the front
panel. The current IP address can be observed on
the TCP/IP Network Properties display.
Response
The WX2184C will return the present IP address value similar to the following: 0.0.0.0
WX2184C
User Manual
4-156
interruption in the LAN communication. When
communication fails, the WX2184C reverts
```
automatically to local (front panel) operation.
```
Response
The WX2184C will return the present keep-alive time-out value.
```
SYSTem:KEEPalive:PROBes<probes>(?)
```
Description
This command programs the number of probes that are used by the keep-alive sequence. The keep-alive
mode assures that LAN connection remains uninterrupted throughout the duration of the LAN interfacing.
Parameters
Name Range Type Default Description
<probes> 2 to 10 Numeric 2 Programs the number of probes that are used by the
keep-alive sequence. The time-out period is initiated
when the LAN is idle for more than the time-out
period and the LAN will be probed as many times as
programmed by this parameter to check if there is an
interruption in the LAN communication. When
communication fails, the WX2184C reverts
```
automatically to local (front panel) operation.
```
Response
The WX2184C will return the present keep-alive number of probes.
WX2184C
User Manual
4-158
```
SYSTem:LXI:VERSion?
```
Description
Response
The WX2184C will return 1.2 with internal flash size of 16Mbyte or 1.4 with internal flash size of 32Mbyte.
```
SYSTem:LXI:IDENtify {OFF | ON | 0 | 1}(?)
```
Description
Use this command to turn the LXI Identify Indicator on the display on or off
Parameters
Range Type Default Description
0-1 Discrete 0 Turns on or off the LXI indicator.
Response
The WX2184C will return 0 or 1 depending on the current LXI indicator state.
```
SYSTem: LXI:MDNS:ENABle{OFF | ON | 0 | 1}(?)
```
Description
```
Use this command to disable or enable the Multicast Domain Name System (mDNS)
```
Parameters
Range Type Default Description
0-1 Discrete 0 Turn on or off the mDNS
Response
The WX2184C will return 0 or 1 depending on the current mDNS state.
```
SYSTem: LXI:MDNS:HNAMe?
```
Description
Use this command to query the resolved mDNS hostname
Response
The WX2184C will return the mDNS hostname.
WX2184C
User Manual
4-160
Store/Recall
Commands
Use these commands to store instrument settings. The store
command collects the current front panel setting and parameters
and stores them in a dedicated memory cell. The store operation
can include front panel settings and current waveforms but, due to
memory limitations, you may select to keep settings only without
waveforms or waveforms only without settings. The store/recall
commands are summarized in Table 4-17.
Table 4-17, Store/Recall Commands Summary
Keyword Parameter Form Default Notes
:SYSTem
:STORe
:CELL 1 to 9 1
:CLEar Clears memory cell
:CONFig SETup | WAVE | ALL ALL
:TARGet INTernal | USB INT
:UPDate
:RECall
:CELL 1 to 9 1
:TARGet INTernal | USB INT
:UPDate
```
SYSTem:STORe:CELL<cell_number>(?)
```
Description
This command selects a memory cell. The selected memory cell will become the target for the store
operation. You may select to store front panel settings, waveforms or both.
Parameters
Name Range Type Description
```
<cell_number> 1 to 9 Numeric (integer
```
```
only)
```
Selects an active memory cell number. Consequent
store commands will affect this cell only.
Response
The WX2184C will return the active memory cell value.
```
SYSTem:STORe:CLEar
```
Description
Use this command to clear the content of a specific memory cell. This will prepare the memory cell to
accept new setup and waveform data.
WX2184C
User Manual
4-162
```
SYSTem:RECall:CELL<cell_number>(?)
```
Description
This command selects a memory cell. The selected memory cell will become the source for the recall
operation. You may select to recall front panel settings, waveforms, or both.
Parameters
Name Range Type Description
```
<cell_number> 1 to 9 Numeric (integer
```
```
only)
```
Selects an active memory cell number. Consequent
recall commands will affect this cell only.
Response
The WX2184C will return the active memory cell value.
```
SYSTem:RECall:TARGet{INTernal|USB}(?)
```
Description
Use this command to select the source of your recall operation. You may select between an internal flash
memory that is limited in size and disk-on-key flash that you can attach to the front panel input. Selecting
the internal option, you may recall waveforms up to 100k long, but external memory has no limitations
except the physical size of the flash on the disk-on-key.
Parameters
Name Type Default Description
INTernal Discrete INT Selects the internal flash memory as the source for the
recall operation. Waveform size for this option is limited
to 100 k points.
USB Discrete Selects the front panel USB input as the source for the
recall operation. Waveform size for this option is limited
only by the size of the disk-on-key flash.
Response
The WX2184C will return INT or USB, depending on the present recall source setting.
```
SYSTem:RECall:UPDate
```
Description
Use this command to update the front panel and arbitrary memory with the information stored in the active
memory cell.
WX2184C
User Manual
4-164
The Store/Recall
File Names
The setup folder contains files that are translated to instrument
settings when downloaded to the WX2184C. These files have
specific and unique file names for the OS to be able to read them
properly. Failure to name the files as requested and understood by
the WX2184C will result in false expectations that the settings were
loaded to the instrument. Therefore, use the names and extensions
exactly as given below. Note that files containing parameter values
contain the name of the parameter and the corresponding channel.
```
setup.txt - is the main image file name (case sensitive!). It contains
```
the entire settings of the generator written as SCPI commands. The
file can be written and edited using MS word or any other word
processor but it must be saved as a text file without attributes and
characters that are not recognized by the WX2184C OS. An
example of this file can be seen in the following pages.
w0000Xc1.wav is a binary file that contains arbitrary waveform
instrument channel 1. Information how to create this file is given in
this chapter. Another option to create this file easily is using the
waveform composer in ArbConnection. Information how to use
ArbConnection to generate an arbitrary waveform is given in a
separate ArbConnection manual. Note in Figure 4-24 that six
```
arbitrary waveform files are shown; each is downloaded to a
```
different segment in channel 1.
d0000Xc1.wav is a binary file that contains digital arbitrary
waveform coordinates in binary format. Information how to create
number where this
instrument channel 1. Another option to create this file easily is
using the waveform composer in ArbConnection. Information how to
use ArbConnection to generate a digital arbitrary waveform is given
in a separate ArbConnection manual.
info.txt - is a meta information text file. It contains information such
as creation date, device model and device model id. Furthermore
seen below.
ahp_fix1.txt is a text file that contains a list of amplitude hopping
values for channel 1. Only one list is allowed per setup.
ahp_var1.txt is a text file that contains a list of amplitude hopping
values and their corresponding dwell time for channel 1. Only one
WX2184C
User Manual
4-166
The Store/Recall
File Structure
If you perform a store operation, the file shown below shows the
entire configuration of the WX2184C. Of course, the values may
look differently but the contents of the file will be similar. You may
use the file examples below to start exerting and compiling your
external file. There are some guidelines that you can use, which will
```
help you minimize the amount of work that you have to do; note the
```
```
following:
```
1. The Setup file contains all of the commands that control the
generator. The file below shows the parameters and
configuration of the example setup. If you do not intend to
change parameter values, reset the generator before the recall
operation and then recall the stored cell. The instrument will
change those parameters that are listed in the file and will not
modify default values that need not be touched.
2. Colon (:) designates a command must follow. The pound signs
designate remarks and are being ignored.
3. If the commands look familiar, this is because these are exactly
the SCPI commands that are being used for remote
programming. If you are familiar with the SCPI concept then it
should be very easy for you to comprehend the usage of these
commands.
4. Channel dependent commands are separated from commands
that are common for both channels. It is recommended that the
order of programming remain as in the Setup file but it is up to
more familiar or friendlier for his application.
5. The Setup file does not include the arbitrary and sequence
configuration, this is specified in the seq_c1 or seq_c2 files.
Each arbitrary waveform is specified in the setup directory,
bearing exactly the name format as specified above. The names
of the file are defined so as to include the segment where they
are to be located and the channel.
6. Following SCPI rules, commands can be used in short or long
format.
Recall Setup3
Example
The Removable Disk folder structure is shown in Figure 4-25 and
the setup, info, seq_c1 files are given below. Note that there are
three arbitrary waveform files w00001c1, w00002c1 and w00003c1.
WX2184C
User Manual
4-168
Info.txt
The above Setup3 file when recalled from the front panel of the unit
will do the following:
Channel 1 & 2 Will be set to Sequence mode with an SCLK of
1GS/s and a sequence table where in step 1 segment1 is repeated
once, step 2 segment2 is repeated twice, and step 3 segment3 is
repeated three times.
Channel 3 & 4 Will be set to standard mode with a square wave
with 50% duty cycle and 10MHz frequency.
Please note that the comments written in the setup line after the
SCPI command are for the benefit of the reader, and must not be
written in the actual setup.txt file that is loaded to the unit.
WX2184C
User Manual
4-170
WX2184C
User Manual
4-172
WX2184C
User Manual
4-174
WX2184C
User Manual
4-176
WX2184C
User Manual
4-178
WX2184C
User Manual
4-180
WX2184C
User Manual
4-182
WX2184C
User Manual
4-184
WX2184C
User Manual
4-186
WX2184C
User Manual
4-188
WX2184C
User Manual
4-190
WX2184C
User Manual
4-192
WX2184C
User Manual
4-194
Model WX2184C-D info file format example:
WX2184C
User Manual
4-196
WX2184C
User Manual
4-198
WX2184C
User Manual
4-200
Error Messages In general, whenever the WX2184C receives an invalid SCPI
command, it automatically generates an error. Errors are stored in a
special error queue and may be retrieved from this buffer one at a
```
time. Errors are retrieved in first-in-first-out (FIFO) order. The first
```
error returned is the first error that was stored. When you have read
all errors from the queue, the generator responds with a 0,"No
error" message.
If more than 30 errors have occurred, the last error stored in the
queue is replaced with -
are stored until you remove errors from the queue. If no errors have
occurred when you read the error queue, the generator responds
with 0,"No error".
The error queue is cleared when power has been shut off or after a
*CLS command has been executed. The *RST command does not
clear the error queue. Use the following command to read the error
```
queue:
```
```
SYSTem:ERRor?
```
```
Errors have the following format (the error string may contain up to
```
```
80 characters):
```
102,"Syntax error".
A complete listing of the errors that can be detected by the
generator is given below.
100,"Command error". When the generator cannot detect more
specific errors, this is the generic syntax error used.
101,"Invalid Character". A syntactic element contains a character,
which is invalid for that type.
102,"Syntax error". Invalid syntax found in the command string.
103,"Invalid separator". An invalid separator was found in the
command string. A comma may have been used instead of a colon
or a semicolon. In some cases where the generator cannot detect a
specific separator, it may return error -100 instead of this error.
104,"Data type error". The parser recognized a data element
different than allowed.
108,"Parameter not allowed". More parameters were received than
expected for the header.
109,"Missing parameter". Too few parameters were received for the
command. One or more parameters that were required for the
command were omitted.
128,"Numeric data not allowed". A legal numeric data element was
received, but the instrument does not accept one in this position.
131,"Invalid suffix". A suffix was incorrectly specified for a numeric
parameter. The suffix may have been misspelled.
WX2184C
User Manual
4-202
eue is full because more than
30 errors have occurred. No additional errors are stored until the
errors from the queue are removed. The error queue is cleared
when power has been shut off, or after a *CLS command has been
executed.
. A command was received which
sends data to the output buffer, but the output buffer contained data
```
from a previous command (the previous data is not overwritten).
```
The output buffer is cleared when power is shut off or after a device
clear has been executed.
```
SYSTem:LOCal
```
Description
```
This command will deactivate the active interface and will restore the WX2184C to local (front panel)
```
operation.
```
SYSTem:VERSion?
```
Description
Query only. This query will interrogate the WX2184C for its current firmware version. The firmware version
is automatically programmed to a secure location in the flash memory and cannot be modified by the user
except when performing firmware update.
Response
The WX2184C will return the current firmware version code in a format similar to the following: 1.15
```
SYSTem:INFormation:CALibration?
```
Description
Query only. This query will interrogate the instrument for its last calibration date.
Response
```
The generator will return the last calibration date in a format similar to the following: 24 Sep 2010 (10
```
```
characters maximum).
```
```
SYSTem:INFormation:MODel?
```
Description
Query only. This query will interrogate the instrument for its model number in a format similar to the
```
following: WX2184C-116. The model number is programmed to a secure location in the flash memory and
```
cannot be modified by the user.
WX2184C
User Manual
4-204
LAN, USB and
GPIB
Programming
Considerations
The Model WX2184C can be programmed from one of three remote
```
interfaces: LAN USB and GPIB. These interfaces not only differ by
```
how they mechanically interface to the instrument but also they are
very different in the way that the instrument reacts to their commands.
For example, the generator does not require any LAN drivers to
connect to a host computer but without a proper USB driver installed
on the computer, the generator will not link and will not receive
commands. There are also hardware issues that differ from interface
to interface, for example, there is one standard in the market for the
USB interface and driving hardware but, on the other hand, the GPIB
triggered competition between vendors that lead to multiple and
parallel development of GPIB interfaces and drivers and, by that,
```
although there is one common standard (IEEE-488.2), each of the
```
interfacing hardware reacts a bit different to commands and has its
own peculiarities when it comes to timing, response and handshaking
principals.
The model WX2184C is supplied with IVI.COM driver that has code
examples and hence eliminates the need to deal with timing issues
that are associated with the different interfaces and more specifically
the driver examples already have the proper delays and pauses that
are mandatory when using some of the GPIB cards so, if you are
problem whatsoever to control instrument parameters and download
waveforms without getting into timing issues that will cause
unpredictable behavior of the generator.
When the generator receives waveform coordinates or table data, the
amount of data that is being transferred to the instrument is huge and
can reach 128,000,000 words of data, if both channels are being
written with waveform data. Waveform coordinates are being
downloaded using special technique, which is described earlier in the
manual so, it is important to remember that, compared to SCPI
commands that may take a few milliseconds to program, downloading
time of waveforms and table data is in the order of many seconds.
Some of the interfaces are not so forgiving when it comes to such
differences in timing, especially when control commands are chained
with waveforms and table data and therefore, one must install the
proper control and suitable handshake that inhibits the flow of data till
the generator is fully ready to accept the next command, query or
waveform coordinates.
In general, the model WX2184C should always be ready to accept
commands but bear in mind that commands are parsed, interpreted
by the firmware and then distributed to various registers and internal
WX2184C
User Manual
4-206
what is the real timeout that is required to execute a command and, in
some case, when an operation exceeds the programmed time out
value, the instruments simply reports that it timed out and the reason
is not always obvious to the programmer. Notice in the attached
program that the timeout value is modified occasionally to match the
require interval that is required to complete the operation safely.
The model WX2184C accepts four types of data from any remote
```
interface:
```
Commands that set and program functions and parameters for the
```
various inputs and outputs of the generator;
```
```
Commands that query current status or generator settings;
```
Data for generating arbitrary waveforms, and
Data for tables such as sequences and memory segmentation.
Commands that control instrument functions and parameters are
programmed using Standard Commands for Programmable
```
Instruments (SCPI commands). These are normally ASCII characters
```
that are parsed and interpreted and converted by the firmware to
control registers and serial trains. Generally, such commands are
parsed in just a few milliseconds so command streams flow to the
generator with practically no delays. This is true for command streams
that do not exceed the input buffer size of 256 characters. However,
commands chain that exceeds the size of 256 characters may chock
the input buffer and therefore it is recommended that programs use
short command strings. For example, one may use the following
command string:
```
Inst:sel 1;:Func:mode user;:trac:def 1,10240;:trac:def 2,
```
```
20480;:trac:def 3, 348;:trac:sel 1;:volt 1.250;offs -0.350;:outp
```
```
1;:inst:sel 2;: Func:mode user;:trac:def 1,10240;:trac:def 2,
```
```
20480;:trac:def 3, 348;:trac:sel 1;:volt 1.250;offs -0.350;:outp 1
```
Depending on the speed of the computer and the interface that is
being used, it is possible that the string will be executed properly
```
however; one should not take the chance because it may cause
```
timeouts and may not be executed properly. Better practice would be
to send the commands one at a time or chain just short strings that
will not overload the input buffer.
No delays between commands or status interrogation is required
when using the following example:
```
Inst:sel 1
```
```
Func:mode user
```
```
trac:def 1,10240;def 2, 20480;def 3, 348; sel 1
```
```
volt 1.250;offs -0.350;:outp 1
```
```
Inst:sel 2
```
WX2184C
User Manual
4-208
available and only then the response should be read. The following
practice is recommended when using multiple queries:
```
*sre16 (enable service request on message available bit - MAV)
```
Query?
ReadSTB and wait till the response it 16
Read the response to the query
The above is recommended as general practice for all queries
however, it is up to the programmer do decide if he wants to query
parameters that he just programmed or eliminate all and just query
```
the generator for errors only (syst:err?). It is also possible to place
```
fixed delays after each query but this method is less efficient and may
accumulate large and unnecessary delays in the program.
Programming the generator with waveform or table data is more of a
```
challenge because there are two parts to this process: 1) the
```
instrument is prepared with ASCII commands to a point where it is
```
ready to receive waveform data and 2) download waveform data.
```
Sounds similar but, in fact, the two processes are completely different.
The commands that prepare the generator for the download process
```
are the same as any control commands; these are simple SCPI
```
commands that select and define the segment number. An example of
segment definition is shown below:
```
func:mode user
```
```
trac:sel 1
```
```
trac:def 1, 2048
```
The above simple example places the generator in arbitrary mode and
selects and defines segment 1 to have a size of 2,048 words of
waveform data.
The next command that starts the download process is
trac#<data_array>. As explained earlier in this chapter, this command
```
has two parts: 1) header, that tells the generator how many bytes are
```
expected to be downloaded. The header part is delimited by the
all ASCII but once
CPU interface bus is rerouted to the arbitrary waveform memory so
the interface has no control over bus activities till the entire waveform
bytes have been transferred to the working memory and only then the
CPU re-enables receipt of control commands over the interface.
It is important to understand that interrupting the binary download
process while the firmware branched out to loop on the downloaded
WX2184C
User Manual
4-210
WX2184C
User Manual
4-212
WX2184C
User Manual
4-214
IEEE-STD-488.2
Common
Commands and
Queries
Since most instruments and devices in an ATE system use similar
commands that perform similar functions, the IEEE-STD-488.2
document has specified a common set of commands and queries
that all compatible devices must use. This avoids situations where
devices from various manufacturers use different sets of commands
to enable functions and report status.
The IEEE-STD-488.2 treats common commands and queries as
device dependent commands. For example, *TRG is sent over the
bus to trigger the instrument. Some common commands and
queries are optional, but most of them are mandatory.
The following is a complete listing of all common-commands and
queries, which are used by the WX2184C
*RST - Resets the generator to its default state.
*TRG - Triggers the generator from the remote interface. This
command affects the generator if it is first placed in the Trigger or
Burst mode of operation and the trigger source is set to "BUS".
*CLS - Clear the Status Byte summary register and all event registers.
*OPC? - Returns "1" to the output buffer after all the previous
commands have been executed. *OPC? is used for synchronization
between a controller and the instrument using the MAV bit in the
Status Byte or a read of the Output Queue. Reading the response to
the *OPC? query has the advantage of removing the complication of
dealing with service requests and multiple polls to the instrument.
However, both the system bus and the controller handshake are in a
temporary hold-off state while the controller is waiting to read the
*OPC? query response.
*STB? - Query the Status Byte summary register. The *STB?
command is similar to a serial poll but is processed like any other
instrument command. The *STB? command returns the same result
```
as a serial poll, but the "request service" bit (bit 6) is not cleared if a
```
serial poll has occurred.
*IDN? -
into four fields, separated by commas. The generator responds with
its manufacturer and model number in the first two fields, and may
also report its serial number and options in fields three and four. If the
latter information is not available, the device must return an ASCII 0
for each.
*OPT? - Returns the instrument option: 1 or 2.