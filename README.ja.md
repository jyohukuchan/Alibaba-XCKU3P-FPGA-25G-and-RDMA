# Alibaba XCKU3P FPGA 25G and RDMA

Alibaba AS02MC04（XCKU3P）向けの、**Corundumベースの25GbE移植・検証プロジェクト**です。
既存のNIC回路とAS02MC04向け10G移植を土台に、25G設定、CDC修正、Vivado互換対応と実機検証を行っています。

## 現在できていること

- CX455A → QSA28 → SFP28 DAC → FPGA の構成で、ネイティブ25GbEの疎通を確認。
- MTU9000・TCP 4並列で、受信側実測約24.75／24.54 Gb/s。方向別に測定しており、同時全二重の値ではありません。
- 各方向100回のpingと、フラグメントしない最大MTUのpingを確認。
- PHY状態信号からVIOへのクロック境界に、6組の2段同期回路を追加。
- 実機で検証したECO版は、`-1-e`品種・25Gクロックのタイミング制約を満たしています。

## まだできていないこと・注意点

- **RDMA／RoCEv2／InfiniBandは未実装・未検証です。** リポジトリ名のRDMAは今後の開発目標です。
- 実機確認したのは配置配線後に同期回路を追加したECO版です。修正版RTLからのクリーンビルド完走と、その生成物の実機検証は残っています。
- TCP再送とMTU1500時の性能課題があります。無損失・全条件ラインレートを保証するものではありません。
- 書き込みはSRAMのみです。電源断でこの25G構成は失われます。フラッシュは変更していません。
- 十分な冷却が必要です。今回の負荷試験は、筐体ファンを高速にした構成で約55℃未満でした。

## 取得とビルド

```bash
git clone --recurse-submodules https://github.com/jyohukuchan/Alibaba-XCKU3P-FPGA-25G-and-RDMA.git
cd Alibaba-XCKU3P-FPGA-25G-and-RDMA
bash scripts/check.sh
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado bash fpga/build_25g.sh
```

Vivado Standard 2025.2とKintex UltraScale+のデバイスファイルが必要です。Lab Editionでは合成できません。
ビルドはハードウェアを書き換えません。新しい生成物は、必ずレポート確認と実機検証が必要です。

詳しくは[英語README](README.md)、[ビルド手順](docs/BUILD.md)、[検証結果](docs/RESULTS.md)、[接続と安全上の注意](docs/HARDWARE.md)を参照してください。

## 出典とライセンス

NIC・MAC/PCS・PCIe DMA・ドライバーの主要部分はCorundum、最初の基板移植はquake0day氏のAS02MC04 port、ピン制約の参照元はFPGA Ninja / Taxiです。
本プロジェクトの追加部分は **BSD-2-Clause-Views** を基本とし、既存ファイルの著作権表示・MIT等の指定を保持します。
[出典と第三者ライセンス](THIRD_PARTY_NOTICES.md)を参照してください。
