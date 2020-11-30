import os
import numpy as np
import matplotlib.pyplot as plt
from tensorflow import keras
import helper
from tfomics import utils, explain, metrics
from six.moves import cPickle
from model_zoo import cnn_deep_exp_nobn
from tensorflow.keras import backend as K

#------------------------------------------------------------------------------------------------


num_trials = 10
model_name = 'cnn-deep'
scales = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 3, 4, 5]

# save path
results_path = utils.make_directory('../results', 'exp_scale_sweep_nobn')
params_path = utils.make_directory(results_path, 'model_params')
save_path = utils.make_directory(results_path, 'conv_filters')


#------------------------------------------------------------------------------------------------

# Define the Gradient Function
def get_gradient_func(model):
    grads = K.gradients(model.total_loss, model.layers[1].kernel)
    inputs = model._feed_inputs + model._feed_targets
    func = K.function(inputs, grads)
    return func

# Define the Required Callback Function
class GradientCalcCallback(keras.callbacks.Callback):
  def on_epoch_end(self, epoch, logs=None):
      get_gradient = get_gradient_func(model)
      grads = get_gradient([x_train, y_train])
      epoch_gradient.append(grads)
      
#------------------------------------------------------------------------------------------------

# load dataset
data_path = '../data/synthetic_dataset.h5'
data = helper.load_data(data_path)
x_train, y_train, x_valid, y_valid, x_test, y_test = data


file_path = os.path.join(results_path, 'performance.tsv')
with open(file_path, 'w') as f:
    f.write('%s\t%s\t%s\n'%('model', 'ave roc', 'ave pr'))

    for scale in scales:
        grads = []
        results = []
        trial_roc_mean = []
        trial_roc_std = []
        trial_pr_mean = []
        trial_pr_std = []
        for trial in range(num_trials):
            keras.backend.clear_session()
                
            # load model
            model = cnn_deep_exp_nobn.model(input_shape=200, scale=scale)

            base_name = model_name+'_'+str(scale)
            name = base_name+'_'+str(trial)
            print('model: ' + name)

            # set up optimizer and metrics
            auroc = keras.metrics.AUC(curve='ROC', name='auroc')
            aupr = keras.metrics.AUC(curve='PR', name='aupr')
            optimizer = keras.optimizers.Adam(learning_rate=0.001)
            loss = keras.losses.BinaryCrossentropy(from_logits=False, label_smoothing=0)
            model.compile(optimizer=optimizer,
                          loss=loss,
                          metrics=['accuracy', auroc, aupr])


            es_callback = keras.callbacks.EarlyStopping(monitor='val_auroc', #'val_aupr',#
                                                        patience=20, 
                                                        verbose=1, 
                                                        mode='max', 
                                                        restore_best_weights=False)
            reduce_lr = keras.callbacks.ReduceLROnPlateau(monitor='val_auroc', 
                                                          factor=0.2,
                                                          patience=5, 
                                                          min_lr=1e-7,
                                                          mode='max',
                                                          verbose=1) 

            # Define the Gradient Fucntion
            epoch_gradient = []
            history = model.fit(x_train, y_train, 
                                epochs=100,
                                batch_size=100, 
                                shuffle=True,
                                validation_data=(x_valid, y_valid), 
                                callbacks=[es_callback, reduce_lr])#, GradientCalcCallback()])

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

            #trial_roc_mean.append(mean_vals[1])
            #trial_roc_std.append(std_vals[1])
            #trial_pr_mean.append(mean_vals[2])
            #trial_pr_std.append(std_vals[2])
            vals = history.history

            results.append([vals['loss'], vals['auroc'], vals['aupr'], vals['val_loss'], vals['val_auroc'], vals['val_aupr']])

        

            #grad = []
            #for i in range(len(epoch_gradient)):
            #    grad.append(np.reshape(epoch_gradient[i][0], (-1,)))
            #grads.append(grad)


        # pickle results
        file_path = os.path.join(results_path, base_name+"_history.pickle")
        with open(file_path, 'wb') as f:
            cPickle.dump(results, f, protocol=cPickle.HIGHEST_PROTOCOL)
            #cPickle.dump(grads, f, protocol=cPickle.HIGHEST_PROTOCOL)
