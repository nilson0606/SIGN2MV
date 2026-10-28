# RMVPE inference attribution

Source: https://github.com/xavriley/RMVPE/blob/37a4b6254c4fa6eb73898177aa4e70749eb665f3/rmvpe/inference.py
Apache-2.0, included in LICENSE. Based on RMVPE by Haojie Wei, Xueke Cao, Tangpeng Dan and Yueguo Chen: https://github.com/Dream-High/RMVPE and https://arxiv.org/abs/2306.15412 .

Local modifications: require an explicit checkpoint managed by the application and load tensor weights with `weights_only=True`. Chunking, download verification and application integration are outside this vendored file. No voice-conversion functionality is used.

Checkpoint: https://huggingface.co/lj1995/VoiceConversionWebUI/blob/main/rmvpe.pt (repository declares MIT). SHA256: 6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193. Not redistributed in this repository.
