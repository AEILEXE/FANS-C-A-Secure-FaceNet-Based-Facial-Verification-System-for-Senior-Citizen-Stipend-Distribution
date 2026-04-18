import sys
import threading

from django.apps import AppConfig


class VerificationConfig(AppConfig):
    name = 'verification'
    verbose_name = 'Verification'
    default = True

    def ready(self):
        """
        Warm up FaceNet + MTCNN in a background daemon thread on Django startup.

        Why: keras-facenet loads ~90 MB of weights on first use. Without warmup,
        the very first call to verify_submit (which computes an embedding) will
        block for 5-15 seconds while TensorFlow builds the graph. Subsequent calls
        are fast because the model is already in memory.

        The background thread is a daemon so it never prevents shutdown. If the
        warmup is still running when the first real verification arrives, get_facenet_model()
        will block briefly until the global _facenet_model is set, which is fine.
        """
        def _warmup():
            try:
                from verification.face_utils import get_facenet_model, _get_mtcnn
                import verification.face_utils as _fu

                print('[FANS-C] Warming up FaceNet model (background)...', file=sys.stderr, flush=True)
                get_facenet_model()

                if not _fu._using_mock:
                    _get_mtcnn()
                    print('[FANS-C] FaceNet + MTCNN ready. First verification will be fast.', file=sys.stderr, flush=True)
                else:
                    print(
                        '[FANS-C] FaceNet model not loaded (mock/fallback mode). '
                        'Check TensorFlow + keras-facenet installation.',
                        file=sys.stderr, flush=True,
                    )
            except Exception as exc:
                print(f'[FANS-C] Model warmup failed: {exc}', file=sys.stderr, flush=True)

        t = threading.Thread(target=_warmup, daemon=True, name='fans-facenet-warmup')
        t.start()
