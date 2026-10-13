from paddleocr import PaddleOCR
import os


# ============================================================
# PADDLE OCR INITIALIZATION
# ============================================================

ocr = PaddleOCR(
    lang="en",

    # IMPORTANT:
    # Disable MKL-DNN / OneDNN.
    # This avoids the ConvertPirAttribute2RuntimeAttribute
    # error occurring on CPU inference.
    enable_mkldnn=False,

    # CPU mode
    device="cpu",

    # We only need normal text OCR.
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,

    # Keep inference simple
    use_tensorrt=False
)


# ============================================================
# EXTRACT TEXT
# ============================================================

def extract_text(image_path):

    if not os.path.exists(image_path):

        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    try:

        print()
        print("==============================================")
        print("PADDLE OCR")
        print("==============================================")

        print("Image:", image_path)
        print("Running OCR...")

        # PaddleOCR 3.x uses predict()
        results = ocr.predict(
            input=image_path
        )

        texts = []

        # ----------------------------------------------------
        # READ RESULTS
        # ----------------------------------------------------

        for result in results:

            data = None

            # PaddleOCR result object
            if hasattr(result, "json"):

                try:
                    data = result.json

                    if callable(data):
                        data = data()

                except Exception:
                    data = None

            # Dictionary result
            if isinstance(data, dict):

                # Newer PaddleOCR versions may store
                # recognition information inside "res".
                if isinstance(
                    data.get("res"),
                    dict
                ):

                    data = data["res"]

                rec_texts = data.get(
                    "rec_texts",
                    []
                )

                if rec_texts:

                    for text in rec_texts:

                        if text:

                            texts.append(
                                str(text).strip()
                            )

            # Some versions expose attributes directly
            elif hasattr(
                result,
                "rec_texts"
            ):

                try:

                    rec_texts = result.rec_texts

                    if rec_texts:

                        for text in rec_texts:

                            if text:

                                texts.append(
                                    str(text).strip()
                                )

                except Exception:
                    pass


        # ----------------------------------------------------
        # CLEAN TEXT
        # ----------------------------------------------------

        texts = [
            text
            for text in texts
            if text
        ]

        final_text = "\n".join(
            texts
        )

        print()
        print("OCR RESULT:")
        print(final_text)

        print()
        print(
            "OCR text count:",
            len(texts)
        )

        print("==============================================")
        print("OCR COMPLETED")
        print("==============================================")
        print()

        return final_text


    except Exception as e:

        print()
        print("==============================================")
        print("OCR ERROR")
        print("==============================================")

        print(
            type(e).__name__,
            ":",
            str(e)
        )

        print("==============================================")
        print()

        raise