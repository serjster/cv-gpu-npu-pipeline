#pragma once
#include <vector>
#include <algorithm>
#include <iostream>
#include <string>

namespace observer_pattern {
// Observer Pattern: Defines a one-to-many dependency between objects so that when one
// object changes state, all its dependents are notified and updated automatically.

// Subject interface
struct Observer {
	virtual ~Observer() = default;
	virtual void Update(float temperature, float humidity, float pressure) = 0;
};

struct Subject {
	virtual ~Subject() = default;
	virtual void RegisterObserver(Observer* observer) = 0;
	virtual void RemoveObserver(Observer* observer) = 0;
	virtual void NotifyObservers() = 0;
};

// Display interface
struct DisplayElement {
	virtual ~DisplayElement() = default;
	virtual void Display() = 0;
};

// Concrete Subject: WeatherData
class WeatherData : public Subject {
private:
	std::vector<Observer*> observers;
	float temperature;
	float humidity;
	float pressure;

public:
	void RegisterObserver(Observer* observer) override {
		observers.push_back(observer);
	}

	void RemoveObserver(Observer* observer) override {
		observers.erase(std::remove(observers.begin(), observers.end(), observer), observers.end());
	}

	void NotifyObservers() override {
		for (auto* observer : observers) {
			observer->Update(temperature, humidity, pressure);
		}
	}

	void MeasurementsChanged() {
		NotifyObservers();
	}

	void SetMeasurements(float temp, float humid, float press) {
		std::cout << "\n";
		std::cout << "Weather data changed: " << temp << ", " << humid << ", " << press << "\n";
		temperature = temp;
		humidity = humid;
		pressure = press;
		MeasurementsChanged();
	}
};

// Concrete Observers
class CurrentConditionsDisplay : public Observer, public DisplayElement {
private:
	float temperature;
	float humidity;
	Subject* weatherData;

public:
	explicit CurrentConditionsDisplay(Subject* wd) : weatherData(wd) {
		weatherData->RegisterObserver(this);
	}

	void Update(float temp, float humid, float pressure) override {
		temperature = temp;
		humidity = humid;
		Display();
	}

	void Display() override {
		std::cout << std::endl;
		std::cout << "Current conditions: " << temperature
				  << "F degrees and " << humidity << "% humidity\n";
	}
};

class StatisticsDisplay : public Observer, public DisplayElement {
private:
	float maxTemp = 0.0f;
	float minTemp = 200.0f;
	float tempSum = 0.0f;
	int numReadings = 0;
	Subject* weatherData;

public:
	explicit StatisticsDisplay(Subject* wd) : weatherData(wd) {
		weatherData->RegisterObserver(this);
	}

	void Update(float temp, float humid, float pressure) override {
		tempSum += temp;
		numReadings++;

		if (temp > maxTemp) maxTemp = temp;
		if (temp < minTemp) minTemp = temp;

		Display();
	}

	void Display() override {
		std::cout << std::endl;
		std::cout << "Avg/Max/Min temperature = " << (tempSum / numReadings)
				  << "/" << maxTemp << "/" << minTemp << "\n";
	}
};

class ForecastDisplay : public Observer, public DisplayElement {
private:
	float currentPressure = 29.92f;
	float lastPressure;
	Subject* weatherData;

public:
	explicit ForecastDisplay(Subject* wd) : weatherData(wd) {
		weatherData->RegisterObserver(this);
	}

	void Update(float temp, float humid, float pressure) override {
		lastPressure = currentPressure;
		currentPressure = pressure;
		Display();
	}

	void Display() override {
		std::cout << std::endl;
		std::cout << "Forecast: ";
		if (currentPressure > lastPressure) {
			std::cout << "Improving weather on the way!\n";
		} else if (currentPressure == lastPressure) {
			std::cout << "More of the same\n";
		} else {
			std::cout << "Watch out for cooler, rainy weather\n";
		}
	}
};

// Usage example
inline void ObserverPatternDemo() {
	WeatherData weatherData;

	CurrentConditionsDisplay currentDisplay(&weatherData);
	StatisticsDisplay statsDisplay(&weatherData);
	ForecastDisplay forecastDisplay(&weatherData);

	weatherData.SetMeasurements(80, 65, 30.4f);
	weatherData.SetMeasurements(82, 70, 29.2f);
	weatherData.SetMeasurements(78, 90, 29.2f);
}
}  // namespace observer_pattern