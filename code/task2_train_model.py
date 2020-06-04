import os
import numpy as np
import matplotlib.pyplot as plt
from tensorflow import keras
import helper
from tfomics import utils, explain

#------------------------------------------------------------------------------------------------

num_trials = 10
model_names = ['cnn-deep', 'cnn-2', 'cnn-50']
activations = ['relu', 'exponential', 'sigmoid', 'tanh', 'softplus', 'linear', 'elu',
               'shift_scale_relu', 'shift_scale_tanh', 'shift_scale_sigmoid', 'exp_relu', 
               'shift_relu', 'scale_relu', 'shift_tanh', 'scale_tanh', 'shift_sigmoid', 'scale_sigmoid']

# save path
results_path = utils.make_directory('../results', 'task2')
params_path = utils.make_directory(results_path, 'model_params')
save_path = utils.make_directory(results_path, 'conv_filters')

#------------------------------------------------------------------------------------------------

# load dataset
data_path = '../data/invivo_dataset.h5'
data = helper.load_dataset(data_path)
x_train, y_train, x_valid, y_valid, x_test, y_test = data

# save results to file
save_path = os.path.join(results_path, 'task2_classification_performance.tsv')
with open(save_path, 'w') as f:
    f.write('%s\t%s\t%s\n'%('model', 'ave roc', 'ave pr'))

    results = {}
    for model_name in model_names:
        results[model_name] = {}
        for activation in activations:
            trial_roc_mean = []
            trial_roc_std = []
            trial_pr_mean = []
            trial_pr_std = []
            for trial in range(num_trials):
                keras.backend.clear_session()
                
                # load model
                model = helper.load_model(model_name, 
                                                activation=activation, 
                                                input_shape=1000)
                name = model_name+'_'+activation+'_'+str(trial)
                print('model: ' + name)

                # compile model
                helper.compile_model(model)

                # setup callbacks
                callbacks = helper.get_callbacks(monitor='val_aupr', patience=20, 
                                          decay_patience=5, decay_factor=0.2)

                # fit model
                history = model.fit(x_train, y_train, 
                                    epochs=100,
                                    batch_size=100, 
                                    shuffle=True,
                                    validation_data=(x_valid, y_valid), 
                                    callbacks=callbacks)

                # save model
                weights_path = os.path.join(params_path, name+'.hdf5')
                model.save_weights(weights_path)
                         
                # get 1st convolution layer filters
                fig, W, logo = explain.plot_filers(model, x_test, layer=3, threshold=0.5, 
                                                   window=20, num_cols=8, figsize=(30,5))
                outfile = os.path.join(save_path, name+'.pdf')
                fig.savefig(outfile, format='pdf', dpi=200, bbox_inches='tight')
                plt.close()

                # clip filters about motif to reduce false-positive Tomtom matches 
                W_clipped = utils.clip_filters(W, threshold=0.5, pad=3)
                output_file = os.path.join(save_path, name+'.meme')
                utils.meme_generate(W_clipped, output_file) 

                # predict test sequences and calculate performance metrics
                predictions = model.predict(x_test)                
                mean_vals, std_vals = metrics.calculate_metrics(y_test, predictions, 'binary')

                trial_roc_mean.append(mean_vals[1])
                trial_roc_std.append(std_vals[1])
                trial_pr_mean.append(mean_vals[2])
                trial_pr_std.append(std_vals[2])

            f.write("%s\t%.3f+/-%.3f\t%.3f+/-%.3f\n"%(name, 
                                                      np.mean(trial_roc_mean),
                                                      np.std(trial_roc_mean), 
                                                      np.mean(trial_pr_mean),
                                                      np.std(trial_pr_mean)))
            results[model_name][activation] = np.array([trial_roc_mean, trial_pr_mean])

# pickle results
file_path = os.path.join(results_path, "task2_performance_results.pickle")
with open(file_path, 'wb') as f:
    cPickle.dump(results, f, protocol=cPickle.HIGHEST_PROTOCOL)

