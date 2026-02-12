def find_all_rad_vel():
    # data correction
    # gaussian fit
    import numpy as np
    from scipy.optimize import curve_fit, OptimizeWarning
    import warnings
    import numpy as np
    from scipy.optimize import curve_fit, OptimizeWarning
    import warnings

    def gauss_fit(x, y, background=None):
        def Gauss(x, A, mu, sigma, bg):
            return A * np.exp(- (x - mu)**2 / (2 * sigma**2)) + bg

        def estimate_initials(x, y):
            total = np.sum(y)
            mu = np.sum(x * y) / total
            sigma = np.sqrt(np.sum(y * (x - mu)**2) / total)
            A = np.max(y)
            return A, mu, sigma

        # Normalize y to prevent numerical issues
        y_max = np.max(np.abs(y))
        if y_max == 0:
            print("Warning: y values are all zero.")
            return None

        y_scaled = y / y_max

        if background is None:
            bg_guess = np.min(y_scaled)
        else:
            bg_guess = background / y_max

        try:
            A_guess, mu_guess, sigma_guess = estimate_initials(x, y_scaled)
            initial_guess = [A_guess, mu_guess, sigma_guess, bg_guess]
        except Exception as e:
            print(f"Initial guess error: {e}")
            return None

        bounds = (
            [0, min(x), 1e-12, -np.inf],  # sigma must be > 0
            [np.inf, max(x), np.inf, np.inf]
        )

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('error', category=OptimizeWarning)
                popt, pcov = curve_fit(
                    Gauss, x, y_scaled, p0=initial_guess,
                    bounds=bounds, maxfev=100000
                )
        except (RuntimeError, ValueError, OptimizeWarning) as e:
            print(f"Fit failed: {e}")
            return None

        # Rescale amplitude and background
        popt[0] *= y_max  # A
        popt[3] *= y_max  # bg

        return popt  # A, mu, sigma, bg



    def gauss_fit_min(x, y):
        from scipy.optimize import curve_fit, OptimizeWarning
        import warnings

        def Gauss(x, A, mu, sigma, background):
            return A * np.exp(- (x - mu)**2 / (2 * sigma**2)) + background

        # Initial guess for parameters A, mu, sigma
        initial_guess = [np.min(y) - np.max(y), np.mean(x), np.std(x), np.max(y)]

        #print('initial guess: amplitude = ',initial_guess[0])
        #print('initial guess: center = ',initial_guess[1])
        #print('initial guess: sigma = ',initial_guess[2])
        #print('initial guess: background = ',initial_guess[3])
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('error', category=OptimizeWarning)
                parameters, covariance = curve_fit(Gauss, x, y, p0=initial_guess, maxfev=100000)
        except (RuntimeError, ValueError, OptimizeWarning) as e:
            print("Optimal parameters not found: ", str(e))
            return None
        amp, mean, stddev, background = parameters
        #print('fitted values: ',amp,mean,stddev,background)
        return amp, mean, stddev, background



    # generating the gaussian function
    def gauss_gen(A, mu, sigma, x, background=None):
        return A * np.exp(- (x - mu)**2 / (2 * sigma**2)) + background if background is not None else A * np.exp(- (x - mu)**2 / (2 * sigma**2))

    # fit gaussian
    def gauss_fit_gen(data_table,low_index, high_index, wLen_test, i,j):#,element,wLen_ele,row,oneD):

        import numpy as np
        import matplotlib.pyplot as plt
        from scipy.optimize import curve_fit

        wLen_obs = np.array(data_table[i][0][low_index:high_index])
        flux_obs = np.array(data_table[i][j][low_index:high_index])

        parameters = gauss_fit(wLen_obs, flux_obs, background=None)

        if parameters is None:
            return None

        amp, mean, stddev, bg = parameters

        # print(f"wavelength: {mean}")

        

        #return amp, mean, stddev


        # x_fit = np.linspace(min(wLen_obs), max(wLen_obs), 1000)
        # flux_fit = gauss_gen(amp, mean, stddev, x_fit, background=bg)

        # flux_lab = gauss_gen(amp,wLen_test,stddev,x_fit)

        # plt.plot(wLen_obs, flux_obs, label='Real Data')
        # plt.plot(x_fit, flux_fit, label='Fitted Gaussian', linestyle='--')
        # plt.plot(x_fit, flux_lab, label="Lab Gaussian", linestyle="-.")
        # plt.xlabel('Wavelength')
        # plt.ylabel('Flux')
        # #plt.title("Chi Square Fit of Object "+ str(object)+ ", Row: "+ str(row)+ ", Element: "+ str(element)+ ", Line: "+ str(wLen_ele))
        # plt.legend()
        # plt.show()


        return (amp,mean,stddev)#,wLen_obs)


    def chi_sq(spec_obs, wLen_obs, amp, mean, stddev, low_index,high_index):

        import numpy as np
        import matplotlib.pyplot as plt
        from scipy.stats import chi2

        total = []
        c = 3e8  # speed of light in m/s

        wLen_obs = wLen_obs[low_index:high_index]

        # Loop over speed range in km/s
        for i in range(-200, 201):
            speed = i * 1e3  # convert to m/s
            dop_mean = (1 + speed / c) * mean
            slit_real = gauss_gen(amp, dop_mean, stddev, wLen_obs)#,background)

            # # Interpolate the observed spectrum to align with Doppler-shifted wavelengths
            # slit_obs_interp = np.interp(dop_wLen, wLen_obs, spec_obs[low_index:high_index])

            # # Calculate chi-square value
            # chi_square = np.sum(((slit_obs_interp - slit_real) ** 2) )

            chi_square = np.sum((spec_obs[low_index:high_index]-slit_real)**2)
            total.append(chi_square)

        v_range = np.linspace(-200, 200, 401)
        parameters = gauss_fit_min(v_range, total)
        if parameters is None:
            return None


        # Fit a Gaussian to the chi-square values to find the minimum
        amp_fit, mean_fit, stddev_fit,background = parameters

        #print("chi sq sd: ", stddev_fit)

        fitting_y = gauss_gen(amp_fit, mean_fit, stddev_fit, v_range,background)
        index_fit = np.argmin(fitting_y)
        speed = v_range[index_fit]

        # print("speed is: ", speed)

        # if stddev_fit <= 80 and stddev_fit >= -80:
        #     plt.plot(v_range, total, label='Chi-square values')
        #     plt.plot(v_range, fitting_y, label='Fitted Gaussian', linestyle='--')
        #     plt.xlabel('Velocity (km/s)')
        #     plt.ylabel('Chi-square')
        #     #plt.title("Chi Square Fit of Object "+ str(object)+ ", Row: "+ str(row)+ ", Element: "+ str(element)+ ", Line: "+ str(wLen_ele))
        #     plt.legend()
        #     plt.show()
        # else:
        #     return None

        return speed