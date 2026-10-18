# Alibaba XCKU3P FPGA 25G and RDMA

Alibaba AS02MC04（XCKU3P）向けの、**Corundumベースの25GbE移植・検証プロジェクト**です。
既存のNIC回路とAS02MC04向け10G移植を土台に、25G設定、CDC修正、Vivado互換対応と実機検証を行っています。

## 現在できていること

- CX455A → QSA28 → SFP28 DAC → FPGA の構成で、ネイティブ25GbEの疎通を確認。
- MTU9000・TCP 4並列で、受信側実測約24.75／24.54 Gb/s。方向別に測定しており、同時全二重の値ではありません。
- 各方向100回のpingと、フラグメントしない最大MTUのpingを確認。
- PHY状態信号からVIOへのクロック境界に、6組の2段同期回路を追加。
- RoCE有効のクリーンRTL版も、`-1-e`品種・25Gクロックのsetup/hold・38件のバススキューなどの最終ゲートを通過。
- **FPGA自身からCX455AへのIPv4 RoCEv2 RC WRITE送信を実機確認。** 64B、65B×3（PSN折り返し）、4KiB×3、64MiBの全受信バイトが一致。
- 64MiBの有限転送は、FPGA時間カウンター基準・初期化/送信完了待ち込みで **約24.264 Gb/s**。ソフトウェアRXEでの代替ではありません。
- ACKを意図的に遮断した実機再送、10msの制御タイムアウト、安全な送信停止・受信復元、その後の正常WRITEを確認。
- **新しいREAD/WRITE統合版で、FPGAからCX455AのメモリをREADし、FPGA内RAMの実データをPCIe経由で全バイト照合。** 端数長・分割応答・PSN折り返し・256KiB全領域・4,096回のREADを含む8ケースと、同じイメージでのWRITE回帰2ケースが不一致ゼロ。
- 設定エラー→アプリ内CLEAR→正常READの復旧も実機確認。統合版はSRAMに書き込み済みで、従来WRITE003は復旧用に保持しています。

## まだできていないこと・注意点

- 実装範囲は、有限パターンのWRITEと、相手メモリをFPGA内の保護された256KiB RAMへ取り込むREADです。相手からのSEND/WRITE受付、READ要求への応答、任意のホストメモリDMA、FPGA側の汎用verbsプロバイダー、ネイティブInfiniBandは未実装です。
- READは1回最大64KiB、最大4,096回、64B単位の格納領域の合計が256KiB以内です。実機確認したREAD同時発行枠は1と2。今回の統合版試験は短い機能確認で、持続帯域・長時間安定性を測定していません。
- キュー転送・端数・PSN折り返し・限定したACK欠落/復旧は確認済みです。任意の障害・輻輳条件や、生産運用の信頼性は保証しません。
- 試験済み生成物はSHA256で特定しています。別設定や再ビルドした生成物が、自動的に実機検証済みになるわけではありません。
- TCP再送とMTU1500時の性能課題があります。無損失・全条件ラインレートを保証するものではありません。
- 書き込みはSRAMのみです。電源断でこの25G構成は失われます。フラッシュは変更していません。
- 十分な冷却が必要です。過去のEthernet負荷試験はファンHighで約55℃未満、今回の短い64MiB RoCE試験はMediumを維持し観測60.32〜60.62℃でした。長時間の冷却余裕を保証する値ではありません。

最新の[実機WRITE記録](results/2026-10-18/rocev2-native-003.json)、[再送・復旧記録](results/2026-10-18/rocev2-native-retry-recovery-003.json)、[開発進捗・制限事項](docs/ROCEV2_PROGRESS.md)を参照してください。
新しい統合版の[READ/WRITE実機記録](results/2026-10-18/rocev2-rw-native-001.json)と[READの結果・使用手順](docs/ROCEV2_READ_RESULTS.md)は別に記録しています。WRITE003の帯域・再送結果を統合版へ転用してはいません。

## 取得とビルド

```bash
git clone --recurse-submodules https://github.com/jyohukuchan/Alibaba-XCKU3P-FPGA-25G-and-RDMA.git
cd Alibaba-XCKU3P-FPGA-25G-and-RDMA
bash scripts/check.sh
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado bash fpga/build_25g.sh
```

Vivado Standard 2025.2とKintex UltraScale+のデバイスファイルが必要です。Lab Editionでは合成できません。
ビルドはハードウェアを書き換えません。新しい生成物は、必ずレポート確認と実機検証が必要です。
上記はEthernet向けの既定ビルドです。RoCE版には、[rdmaの手順](rdma/README.md)に従ったHLS生成物も必要です。

詳しくは[英語README](README.md)、[ビルド手順](docs/BUILD.md)、[検証結果](docs/RESULTS.md)、[接続と安全上の注意](docs/HARDWARE.md)を参照してください。

## 出典とライセンス

NIC・MAC/PCS・PCIe DMA・ドライバーの主要部分はCorundum、最初の基板移植はquake0day氏のAS02MC04 port、ピン制約の参照元はFPGA Ninja / Taxiです。
本プロジェクトの追加部分は **BSD-2-Clause-Views** を基本とし、既存ファイルの著作権表示・MIT等の指定を保持します。
[出典と第三者ライセンス](THIRD_PARTY_NOTICES.md)を参照してください。
