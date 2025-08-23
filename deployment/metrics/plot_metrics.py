from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml


class PlotGithubMetrics:

    @staticmethod
    def plot(target_env):
        p =  Path(__file__).parent / f"metrics_{target_env}.yaml"

        with open(p, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)

        releases = data['dot_releases']
        df = pd.DataFrame(releases)
        df['date'] = pd.to_datetime(df['date'])

        # Calculate cumulative sums
        df['Cumulative Count Zip Downloads'] = df['count_zip_downloads'].cumsum()
        df['Cumulative App Version Downloads'] = df['app_version_downloads'].cumsum()
        df['Cumulative Bridgectl Setup Downloads'] = df['bridgectl_setup_downloads'].cumsum()

        # Plot the data
        plt.figure(figsize=(10, 6))
        plt.plot(df['date'], df['Cumulative Count Zip Downloads'], marker='o', label='Cumulative Count Zip Downloads')
        plt.plot(df['date'], df['Cumulative App Version Downloads'], marker='o', label='Cumulative App Version Downloads')
        plt.plot(df['date'], df['Cumulative Bridgectl Setup Downloads'], marker='o', label='Cumulative Bridgectl Setup Downloads')

        # Customize the chart
        plt.title('BridgeCTL - Cumulative Downloads for the Private Customer Beta')
        plt.xlabel('Date')
        plt.ylabel('Downloads')
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)

        # Display the chart
        plt.tight_layout()
        plt.show()

        csv_file =  Path(__file__).parent / f"metrics_{target_env}.csv"
        df.to_csv(csv_file, index=False)