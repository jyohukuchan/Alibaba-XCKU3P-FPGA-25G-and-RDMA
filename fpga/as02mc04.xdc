# SPDX-License-Identifier: BSD-2-Clause-Views AND MIT
# Copyright (c) 2019-2023 The Regents of the University of California
# Copyright (c) 2025-2026 FPGA Ninja, LLC
# Derived from the AS02MC04 port by quake0day; see THIRD_PARTY_NOTICES.md.
# XDC constraints for the Alibaba AS02MC04 / YZQT-02337-101
# part: xcku3p-ffvb676-1-e
# Ported from Corundum Nexus_K3P_S/fpga_k3p.xdc; pin LOCs from
# fpganinja/taxi src/cndm/board/AS02MC04 (Alex Forencich).
#
# Top-level port names kept identical to corundum fpga_k3p.v EXCEPT:
#   clk_10mhz            -> clk_100mhz_p/clk_100mhz_n  (100MHz LVDS diff)
#   BPI flash_* ports    -> REMOVED (AS02MC04 uses QSPI SPIx4 via STARTUPE3)
#   sma_* ports          -> REMOVED (no SMA on AS02MC04)
#   sfp_*_tx_disable/rs  -> REMOVED (no such pins on AS02MC04; tie off in RTL)

# General configuration (SPIx4 QSPI, 256Mbit)
set_property CFGBVS GND                                      [current_design]
set_property CONFIG_VOLTAGE 1.8                              [current_design]
set_property BITSTREAM.GENERAL.COMPRESS true                 [current_design]
set_property BITSTREAM.CONFIG.UNUSEDPIN Pullup               [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 72.9                [current_design]
set_property CONFIG_MODE SPIx4                               [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4                 [current_design]
set_property BITSTREAM.CONFIG.SPI_FALL_EDGE Yes              [current_design]
set_property BITSTREAM.CONFIG.OVERTEMPSHUTDOWN Enable        [current_design]

# 100 MHz system clock (Y2, LVDS) -> freerun clock
set_property -dict {LOC E18  IOSTANDARD LVDS} [get_ports {clk_100mhz_p}]
set_property -dict {LOC D18  IOSTANDARD LVDS} [get_ports {clk_100mhz_n}]
create_clock -period 10 -name clk_100mhz [get_ports {clk_100mhz_p}]

# LEDs (map corundum sfp_1_led/sfp_2_led/sma_led onto AS02MC04 sfp_led/led)
set_property -dict {LOC B12 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sfp_1_led[0]}] ;# DS3
set_property -dict {LOC C12 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sfp_1_led[1]}] ;# DS2
set_property -dict {LOC B11 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sfp_2_led[0]}] ;# DS6
set_property -dict {LOC C11 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sfp_2_led[1]}] ;# DS7
set_property -dict {LOC A10 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sma_led[0]}]    ;# DS8
set_property -dict {LOC B10 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12} [get_ports {sma_led[1]}]    ;# DS9

set_false_path -to [get_ports {sfp_1_led[*] sfp_2_led[*] sma_led[*]}]
set_output_delay 0 [get_ports {sfp_1_led[*] sfp_2_led[*] sma_led[*]}]

# SFP28 Interfaces (sfp_1 = AS02MC04 sfp[0] X0Y15; sfp_2 = sfp[1] X0Y14; quad 227)
set_property -dict {LOC A4  } [get_ports sfp_1_rx_p] ;# MGTYRXP3_227 GTYE4_CHANNEL_X0Y15
set_property -dict {LOC A3  } [get_ports sfp_1_rx_n] ;# MGTYRXN3_227
set_property -dict {LOC B7  } [get_ports sfp_1_tx_p] ;# MGTYTXP3_227 X0Y15
set_property -dict {LOC B6  } [get_ports sfp_1_tx_n] ;# MGTYTXN3_227
set_property -dict {LOC B2  } [get_ports sfp_2_rx_p] ;# MGTYRXP2_227 GTYE4_CHANNEL_X0Y14
set_property -dict {LOC B1  } [get_ports sfp_2_rx_n] ;# MGTYRXN2_227
set_property -dict {LOC D7  } [get_ports sfp_2_tx_p] ;# MGTYTXP2_227 X0Y14
set_property -dict {LOC D6  } [get_ports sfp_2_tx_n] ;# MGTYTXN2_227
set_property -dict {LOC K7  } [get_ports sfp_mgt_refclk_p] ;# MGTREFCLK0P_227 from Y1 (156.25MHz)
set_property -dict {LOC K6  } [get_ports sfp_mgt_refclk_n] ;# MGTREFCLK0N_227
set_property -dict {LOC D14  IOSTANDARD LVCMOS33 PULLUP true} [get_ports sfp_1_npres]
set_property -dict {LOC E11  IOSTANDARD LVCMOS33 PULLUP true} [get_ports sfp_2_npres]
set_property -dict {LOC D13  IOSTANDARD LVCMOS33 PULLUP true} [get_ports sfp_1_los]
set_property -dict {LOC E10  IOSTANDARD LVCMOS33 PULLUP true} [get_ports sfp_2_los]
set_property -dict {LOC C13  IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12 PULLUP true} [get_ports sfp_i2c_scl]
set_property -dict {LOC C14  IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12 PULLUP true} [get_ports sfp_1_i2c_sda]
set_property -dict {LOC D11  IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12 PULLUP true} [get_ports sfp_2_i2c_sda]

# 156.25 MHz MGT reference clock (period 6.4 ns)
create_clock -period 6.4 -name sfp_mgt_refclk [get_ports sfp_mgt_refclk_p]

set_false_path -from [get_ports {sfp_1_npres sfp_2_npres sfp_1_los sfp_2_los}]
set_input_delay 0 [get_ports {sfp_1_npres sfp_2_npres sfp_1_los sfp_2_los}]

set_false_path -to [get_ports {sfp_1_i2c_sda sfp_2_i2c_sda sfp_i2c_scl}]
set_output_delay 0 [get_ports {sfp_1_i2c_sda sfp_2_i2c_sda sfp_i2c_scl}]
set_false_path -from [get_ports {sfp_1_i2c_sda sfp_2_i2c_sda sfp_i2c_scl}]
set_input_delay 0 [get_ports {sfp_1_i2c_sda sfp_2_i2c_sda sfp_i2c_scl}]

# Board management I2C (map corundum eeprom_i2c -> AS02MC04 i2c J14/J15)
set_property -dict {LOC J14 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12 PULLUP true} [get_ports eeprom_i2c_scl]
set_property -dict {LOC J15 IOSTANDARD LVCMOS33 SLEW SLOW DRIVE 12 PULLUP true} [get_ports eeprom_i2c_sda]

set_false_path -to [get_ports {eeprom_i2c_sda eeprom_i2c_scl}]
set_output_delay 0 [get_ports {eeprom_i2c_sda eeprom_i2c_scl}]
set_false_path -from [get_ports {eeprom_i2c_sda eeprom_i2c_scl}]
set_input_delay 0 [get_ports {eeprom_i2c_sda eeprom_i2c_scl}]

# PCIe Interface (lane LOCs identical to Nexus; refclk MGTREFCLK1_225 T7/T6, reset A9)
set_property -dict {LOC P2  } [get_ports {pcie_rx_p[0]}] ;# MGTYRXP3_225 GTYE4_CHANNEL_X0Y7
set_property -dict {LOC P1  } [get_ports {pcie_rx_n[0]}]
set_property -dict {LOC R5  } [get_ports {pcie_tx_p[0]}] ;# MGTYTXP3_225 X0Y7
set_property -dict {LOC R4  } [get_ports {pcie_tx_n[0]}]
set_property -dict {LOC T2  } [get_ports {pcie_rx_p[1]}] ;# X0Y6
set_property -dict {LOC T1  } [get_ports {pcie_rx_n[1]}]
set_property -dict {LOC U5  } [get_ports {pcie_tx_p[1]}]
set_property -dict {LOC U4  } [get_ports {pcie_tx_n[1]}]
set_property -dict {LOC V2  } [get_ports {pcie_rx_p[2]}] ;# X0Y5
set_property -dict {LOC V1  } [get_ports {pcie_rx_n[2]}]
set_property -dict {LOC W5  } [get_ports {pcie_tx_p[2]}]
set_property -dict {LOC W4  } [get_ports {pcie_tx_n[2]}]
set_property -dict {LOC Y2  } [get_ports {pcie_rx_p[3]}] ;# X0Y4
set_property -dict {LOC Y1  } [get_ports {pcie_rx_n[3]}]
set_property -dict {LOC AA5 } [get_ports {pcie_tx_p[3]}]
set_property -dict {LOC AA4 } [get_ports {pcie_tx_n[3]}]
set_property -dict {LOC AB2 } [get_ports {pcie_rx_p[4]}] ;# X0Y3 (quad 224)
set_property -dict {LOC AB1 } [get_ports {pcie_rx_n[4]}]
set_property -dict {LOC AC5 } [get_ports {pcie_tx_p[4]}]
set_property -dict {LOC AC4 } [get_ports {pcie_tx_n[4]}]
set_property -dict {LOC AD2 } [get_ports {pcie_rx_p[5]}] ;# X0Y2
set_property -dict {LOC AD1 } [get_ports {pcie_rx_n[5]}]
set_property -dict {LOC AD7 } [get_ports {pcie_tx_p[5]}]
set_property -dict {LOC AD6 } [get_ports {pcie_tx_n[5]}]
set_property -dict {LOC AE4 } [get_ports {pcie_rx_p[6]}] ;# X0Y1
set_property -dict {LOC AE3 } [get_ports {pcie_rx_n[6]}]
set_property -dict {LOC AE9 } [get_ports {pcie_tx_p[6]}]
set_property -dict {LOC AE8 } [get_ports {pcie_tx_n[6]}]
set_property -dict {LOC AF2 } [get_ports {pcie_rx_p[7]}] ;# X0Y0
set_property -dict {LOC AF1 } [get_ports {pcie_rx_n[7]}]
set_property -dict {LOC AF7 } [get_ports {pcie_tx_p[7]}]
set_property -dict {LOC AF6 } [get_ports {pcie_tx_n[7]}]
set_property -dict {LOC T7  } [get_ports pcie_refclk_p] ;# MGTREFCLK1P_225 (100MHz)
set_property -dict {LOC T6  } [get_ports pcie_refclk_n] ;# MGTREFCLK1N_225
set_property -dict {LOC A9 IOSTANDARD LVCMOS33 PULLUP true} [get_ports pcie_reset_n]

set_false_path -from [get_ports {pcie_reset_n}]
set_input_delay 0 [get_ports {pcie_reset_n}]

# 100 MHz PCIe MGT reference clock
create_clock -period 10 -name pcie_mgt_refclk [get_ports pcie_refclk_p]
