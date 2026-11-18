def level_meter_0deg_to_volume(level_cm):
    """
    Interpolate 0-degree level meter reading to volume.

    Parameters
    ----------
    level_cm : float or array-like
        Level meter reading in cm.

    Returns
    -------
    volume_L : float or numpy.ndarray
        Interpolated volume in liters.
    """

    import numpy as np

    data = np.array([
        [0.00, 17.430730],
        [10.00, 22.579828],
        [20.00, 27.728926],
        [30.00, 32.878024],
        [40.00, 38.027123],
        [50.00, 43.176221],
        [60.00, 48.325319],
        [70.00, 53.474422],
        [80.00, 58.623527],
        [90.00, 63.772618],
        [100.00, 68.921712],
        [110.00, 74.070811],
        [120.00, 79.219909],
        [130.00, 84.369007],
        [140.00, 89.518105],
        [150.00, 94.667204],
        [160.00, 99.816302],
        [170.00, 104.965400],
        [180.00, 110.114498],
        [190.00, 115.263597],
        [200.00, 120.412695],
        [210.00, 125.561793],
        [220.00, 130.710892],
        [230.00, 135.859990],
        [240.00, 141.009088],
        [250.00, 146.158186],
        [260.00, 151.307285],
        [270.00, 156.456383],
        [280.00, 161.605481],
        [290.00, 166.754579],
        [300.00, 171.903678],
        [310.00, 177.052776],
        [320.00, 182.201874],
        [330.00, 187.350973],
        [340.00, 192.500071],
        [350.00, 197.649169],
        [360.00, 202.798267],
        [370.00, 207.947366],
        [380.00, 213.096464],
        [390.00, 218.245562],
        [400.00, 223.394660],
        [410.00, 228.524454],
        [420.00, 233.632463],
        [430.00, 238.740472],
        [440.00, 243.840760],
        [450.00, 248.886107],
        [460.00, 253.808455],
        [470.00, 258.507961],
        [480.00, 262.810381],
        [490.00, 266.647753],
        [500.00, 270.013751],
        [510.00, 272.902065],
        [520.00, 275.306375],
        [530.00, 277.220349],
        [540.00, 278.667073],
        [550.00, 279.717165],
        [560.00, 280.304337],
        [566.36, 280.409559],
    ])

    height_cm = data[:, 0]/10
    volume_L = data[:, 1]

    level_arr = np.asarray(level_cm, dtype=float)

    V = np.interp(level_arr, height_cm, volume_L)

    return V


def level_meter_to_vol(level_cm, tilt_deg, csv_file="Level Meter - Combined.csv"):
    """
    Interpolate level meter reading and tilt angle to helium volume.

    Parameters
    ----------
    level_cm : float
        Level meter reading in cm.
    tilt_deg : float
        Tilt angle in degrees.
    csv_file : str
        Path to the CSV file containing level meter data.

    Returns
    -------
    volume_L : float
        Interpolated helium volume in liters.
    """

    import numpy as np
    import pandas as pd

    data = pd.read_csv(csv_file)
    volumes = []
    for column in [8, 6, 4, 2, 0]:
        height_mm, volume_L = data.iloc[:, column:column + 2].dropna().to_numpy().T
        volumes.append(np.interp(level_cm, height_mm / 10, volume_L))

    return float(np.interp(tilt_deg, [0, 15, 30, 45, 60], volumes))
