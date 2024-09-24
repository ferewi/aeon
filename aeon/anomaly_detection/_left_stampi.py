"""LeftSTAMPi anomaly detector."""

__maintainer__ = ["ferewi"]
__all__ = ["LeftSTAMPi"]


import numpy as np

from aeon.anomaly_detection.base import BaseAnomalyDetector
from aeon.utils.validation._dependencies import _check_soft_dependencies
from aeon.utils.windowing import reverse_windowing


class LeftSTAMPi(BaseAnomalyDetector):
    """LeftSTAMPi anomaly detector.

    LeftSTAMPi [1]_ calculates the left matrix profile of a time series,
    which is the distance to the nearest neighbor of each subsequence
    in the time series, in an incremental manner. The matrix profile is then
    used to calculate the anomaly score for each time point. The larger the distance to
    the nearest neighbor, the more anomalous the time point is.

    LeftSTAMPi supports univariate time series only.

    .. list-table:: Capabilities
       :stub-columns: 1

       * - Input data format
         - univariate
       * - Output data format
         - anomaly scores
       * - Learning Type
         - unsupervised


    Parameters
    ----------
    window_size : int
        Size of the sliding window.
    n_init_train: int, defaul=None
        The number of points used to init the matrix profile.
        The discord will not be found in this segment.
    normalize : bool, default=True
        Whether to normalize the windows before computing the distance.
    p : float, default=2.0
        The p-norm to use for the distance calculation.
    k : int, default=1
        The number of top distances to return.

    Examples
    --------
    Batch Processing
        Calculate the anomaly score for the complete time series at once.
        Internally,this is applying the incremental approach outlined below.

        >>> import numpy as np # doctest: +SKIP
        >>> from aeon.anomaly_detection import LeftSTAMPi  # doctest: +SKIP
        >>> X = np.random.default_rng(42).random((10))  # doctest: +SKIP
        >>> detector = LeftSTAMPi(window_size=3, n_init_train=3)  # doctest: +SKIP
        >>> detector.fit_predict(X)  # doctest: +SKIP
        array([0.        , 0.        , 0.        , 0.07042306, 0.15989868,
               0.68912499, 0.75398303, 0.89696118, 0.5516023 , 0.69736132])

    Stream Processing
        Calculate the anomaly score incrementally.

        >>> import numpy as np # doctest: +SKIP
        >>> from aeon.anomaly_detection import LeftSTAMPi  # doctest: +SKIP
        >>> X = np.random.default_rng(42).random((10))  # doctest: +SKIP
        >>> X_train, X_stream = X[:3], X[3:]  # doctest: +SKIP
        >>> detector = LeftSTAMPi(window_size=3)  # doctest: +SKIP
        >>> detector.fit(X_train)  # doctest: +SKIP
        >>> score = np.array([]) # doctest: +SKIP
        >>> for x in X_stream: # doctest: +SKIP
        >>>     score = detector.predict(np.array([x]))  # doctest: +SKIP
        array([0.        , 0.        , 0.        , 0.07042306, 0.15989868,
               0.68912499, 0.75398303, 0.89696118, 0.5516023 , 0.69736132])

    References
    ----------
    .. [1] Chin-Chia Michael Yeh, Yan Zhu, Liudmila Ulanova, Nurjahan Begum,
           Yifei Ding, Hoang Anh Dau, Diego Furtado Silva, Abdullah Mueen,
           and Eamonn Keogh: "Matrix Profile I: All Pairs Similarity Joins
           for Time Series: A Unifying View That Includes Motifs, Discords
           and Shapelets.", In Proceedings of the International Conference
           on Data Mining (ICDM), 1317–1322. doi: 10.1109/ICDM.2016.0179

    """

    _tags = {
        "capability:univariate": True,
        "capability:multivariate": False,
        "capability:missing_values": False,
        "fit_is_empty": False,
        "python_dependencies": ["stumpy"],
    }

    def __init__(
        self,
        window_size: int = 3,
        n_init_train: int = None,
        normalize: bool = True,
        p: float = 2.0,
        k: int = 1,
    ):
        self.mp: np.ndarray | None = None
        self.window_size = window_size
        self.n_init_train = n_init_train
        self.normalize = normalize
        self.p = p
        self.k = k

        super().__init__(axis=0)

    def _check_params(self, X):
        if self.window_size < 3 or self.window_size > X.shape[0]:
            raise ValueError(
                "The window size must be at least 3 and at most the length of the "
                "time series."
            )
        if self.window_size > self.n_init_train:
            raise ValueError(
                f"The window size must be less than or equal to "
                f"n_init_train (is: {self.n_init_train})"
            )

        if self.k < 1 or self.k > X.shape[0] - self.window_size:
            raise ValueError(
                "The top `k` distances must be at least 1 and at most the length of "
                "the time series minus the window size."
            )

    def _fit(self, X, y=None):
        self.n_init_train = len(X)
        self._check_params(X)

        if X.ndim > 1:
            X = X.squeeze()
        self._call_stumpi(X)

        return self

    def _predict(self, X: np.ndarray) -> np.ndarray:
        if X.ndim > 1:
            X = X.squeeze()

        self.mp.update(X)

        lmp = self.mp._left_P
        lmp[: self.n_init_train] = 0
        point_anomaly_scores = reverse_windowing(lmp, self.window_size)

        return point_anomaly_scores

    def _fit_predict(self, X, y=None) -> np.ndarray:
        self._check_params(X)

        if X.ndim > 1:
            X = X.squeeze()

        self._call_stumpi(X[: self.n_init_train])

        for x in X[self.n_init_train :]:
            self.mp.update(x)

        lmp = self.mp._left_P
        lmp[: self.n_init_train] = 0

        point_anomaly_scores = reverse_windowing(lmp, self.window_size)

        return point_anomaly_scores

    def _call_stumpi(self, X):
        if _check_soft_dependencies("stumpy", severity="error"):
            import stumpy

            self.mp = stumpy.stumpi(
                X,
                m=self.window_size,
                egress=False,
                normalize=self.normalize,
                p=self.p,
                k=self.k,
            )
