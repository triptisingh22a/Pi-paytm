from ai.sarvam_voice import status


class VoiceAdapter:
    status = "VERIFIED_SCHEMA"

    def capabilities(self):
        return status()
