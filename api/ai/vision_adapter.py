class VisionAdapter:
    status = "UNVERIFIED"

    def parse(self, image):
        raise NotImplementedError(
            "OCR disabled until official provider schema is verified; enter purchases manually"
        )
