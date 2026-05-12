//
// Created by Sergio Soldado on 06/01/2026.
//

#include <adapter.h>
#include <antipatterns.h>
#include <command.h>
#include <composite.h>
#include <compound.h>
#include <decorator.h>
#include <facade.h>
#include <factory.h>
#include <gtest/gtest.h>
#include <iterator.h>
#include <observer.h>
#include <proxy.h>
#include <real_world_examples.h>
#include <singleton.h>
#include <state.h>
#include <strategy.h>
#include <template_method.h>

TEST(DesignPatterns, Observer) {
	using namespace observer_pattern;
	WeatherData weatherData;
	ForecastDisplay forecastDisplay(&weatherData);
	StatisticsDisplay statsDisplay(&weatherData);
	CurrentConditionsDisplay currentDisplay(&weatherData);

	weatherData.SetMeasurements(23, 67, 1.2);
	weatherData.SetMeasurements(31, 87, 1.1);
	weatherData.SetMeasurements(23, 99, 1.1);
	weatherData.SetMeasurements(13, 39, 1.0);
}

TEST(DesignPatterns, Strategy) {
	using namespace strategy_pattern;
	ModelDuck modelDuck;
	MallardDuck mallardDuck;
	RubberDucky rubberDucky;
	{
		Duck& duck = modelDuck;
		duck.Display();
		std::cout << "Wait, let's upgrade the Model Duck!" << std::endl;
		duck.SetFlyBehavior(make_unique<FlyRockerPowered>());
		duck.Display();
	}
	{
		Duck& duck = mallardDuck;
		duck.Display();
	}
	{
		Duck& duck = rubberDucky;
		duck.Display();
	}
}

TEST(DesignPatterns, Factory) {
	using namespace factory_pattern;
	FactoryPatternDemo();
}

